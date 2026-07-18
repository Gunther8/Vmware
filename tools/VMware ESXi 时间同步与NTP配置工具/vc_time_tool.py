#!/usr/bin/env python3
"""
vc_time_tool.py
vCenter 虚拟机时间同步排查 + ESXi 主机 NTP 批量配置工具

依赖：
    pip install pyvmomi

用法示例：

1) 排查所有VM是否开启了"与宿主机同步时间"（修正ESXi时间前必须先看这个）：
    python3 vc_time_tool.py --vcenter vcenter.example.com --user administrator@vsphere.local \
        check-vm-sync --csv vm_time_sync_report.csv

2) 批量取消所有开启了'与主机同步时间'的VM（先dry-run看清单，确认后加--confirm执行）：
    python3 vc_time_tool.py --vcenter vcenter.example.com --user administrator@vsphere.local \
        disable-vm-sync
    python3 vc_time_tool.py --vcenter vcenter.example.com --user administrator@vsphere.local \
        disable-vm-sync --confirm

3) 批量给所有ESXi主机配置NTP服务器并启动ntpd（开机自启，先dry-run看清单，确认后加--confirm执行）：
    python3 vc_time_tool.py --vcenter vcenter.example.com --user administrator@vsphere.local \
        set-ntp --ntp 192.0.2.1
    python3 vc_time_tool.py --vcenter vcenter.example.com --user administrator@vsphere.local \
        set-ntp --ntp 192.0.2.1 --confirm

4) 只对指定几台主机/VM生效：
    python3 vc_time_tool.py --vcenter vcenter.example.com --user administrator@vsphere.local \
        disable-vm-sync --vms VM1 VM2 --confirm
    python3 vc_time_tool.py --vcenter vcenter.example.com --user administrator@vsphere.local \
        set-ntp --ntp 192.0.2.1 --hosts esxi01.example.com esxi02.example.com
"""

import argparse
import atexit
import csv
import getpass
import socket
import ssl
import struct
import sys
import time

from pyVim.connect import SmartConnect, Disconnect
from pyVmomi import vim


# ---------------------------------------------------------------------------
# 基础工具
# ---------------------------------------------------------------------------

def connect_vcenter(host, user, pwd, port=443, disable_ssl_verification=True):
    context = None
    if disable_ssl_verification:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    si = SmartConnect(host=host, user=user, pwd=pwd, port=port, sslContext=context)
    atexit.register(Disconnect, si)
    return si


def get_all_objs(si, vim_type):
    content = si.RetrieveContent()
    container = content.viewManager.CreateContainerView(content.rootFolder, vim_type, True)
    objs = list(container.view)
    container.Destroy()
    return objs


def evaluate_vm_time_sync(cfg):
    """判断VM是否开启了"与主机同步时间"。

    ToolsConfigInfo.syncTimeWithHost 自 vSphere API 7.0 起已被VMware标记为废弃，
    实际由 syncTimeWithHostAllowed 取代（在生产环境用 vc_time_diag.py 实测确认：
    某VM在新版UI里勾选了"在启动和恢复时同步"，syncTimeWithHost=False，但
    syncTimeWithHostAllowed=True）。只读旧字段会导致这批VM全部被误判为"未开启"。
    这里优先信新字段，同时也看一眼旧字段，兼容仍然只用旧字段的老版本Tools/VM。
    """
    if cfg is None or cfg.tools is None:
        return {"sync_time_with_host": None, "sync_legacy_flag": None, "sync_allowed_flag": None}

    legacy_flag = cfg.tools.syncTimeWithHost
    allowed_flag = getattr(cfg.tools, "syncTimeWithHostAllowed", None)

    flags = [f for f in (legacy_flag, allowed_flag) if f is not None]
    combined = any(flags) if flags else None

    return {
        "sync_time_with_host": combined,
        "sync_legacy_flag": legacy_flag,
        "sync_allowed_flag": allowed_flag,
    }


def wait_for_task(task, timeout=300, poll_interval=0.5):
    """等待vCenter task完成。

    用sleep轮询代替忙等，避免占满CPU和高频拉取vCenter属性；
    超过timeout秒仍未结束则抛TimeoutError，避免主机/VM无响应时脚本永久卡死。
    """
    elapsed = 0.0
    while task.info.state not in (vim.TaskInfo.State.success, vim.TaskInfo.State.error):
        time.sleep(poll_interval)
        elapsed += poll_interval
        if elapsed >= timeout:
            raise TimeoutError(f"任务等待超时({timeout}秒)，目标主机/VM可能无响应")
    if task.info.state == vim.TaskInfo.State.error:
        raise Exception(task.info.error.msg)


# ---------------------------------------------------------------------------
# 供GUI等其他程序调用的底层函数（返回数据/对象，不直接print，不耦合CLI）
# ---------------------------------------------------------------------------

def get_vm_sync_rows(si):
    """返回所有VM的时间同步信息，每行附带原始vm对象(key='vm_obj')方便调用方直接操作。"""
    vms = get_all_objs(si, [vim.VirtualMachine])
    rows = []
    for vm in vms:
        cfg = vm.config
        summary = vm.summary
        if cfg is None:
            continue
        sync_info = evaluate_vm_time_sync(cfg)
        host_name = vm.runtime.host.name if vm.runtime.host else "N/A"
        rows.append({
            "vm_obj": vm,
            "vm_name": vm.name,
            "power_state": str(summary.runtime.powerState),
            "esxi_host": host_name,
            "sync_time_with_host": sync_info["sync_time_with_host"],
            "sync_detail": sync_info,
        })
    return rows


def get_host_ntp_rows(si):
    """返回所有ESXi主机的NTP配置信息，每行附带原始host对象(key='host_obj')。"""
    hosts = get_all_objs(si, [vim.HostSystem])
    rows = []
    for host in hosts:
        try:
            dt_info = host.configManager.dateTimeSystem.dateTimeInfo
            servers = list(dt_info.ntpConfig.server) if dt_info.ntpConfig else []
            svc_list = host.configManager.serviceSystem.serviceInfo.service
            ntpd = next((s for s in svc_list if s.key == "ntpd"), None)
            rows.append({
                "host_obj": host,
                "host_name": host.name,
                "current_ntp": ", ".join(servers) if servers else "(未配置)",
                "ntpd_running": bool(ntpd.running) if ntpd else False,
                "ntpd_policy": ntpd.policy if ntpd else "unknown",
                "connection_state": str(host.runtime.connectionState),
            })
        except Exception as e:
            rows.append({
                "host_obj": host, "host_name": host.name, "current_ntp": f"读取失败: {e}",
                "ntpd_running": False, "ntpd_policy": "unknown", "connection_state": "error",
            })
    return rows


def apply_vm_sync(vm, enabled):
    """对单个vm对象设置"与主机同步时间"。

    同时写废弃的旧字段(syncTimeWithHost)和vSphere 7+实际生效的新字段
    (syncTimeWithHostAllowed)，只改前者对新版UI配置的VM不生效（见
    evaluate_vm_time_sync 的说明和 vc_time_diag.py 的实测结果）。
    """
    spec = vim.vm.ConfigSpec()
    spec.tools = vim.vm.ToolsConfigInfo(syncTimeWithHost=enabled, syncTimeWithHostAllowed=enabled)
    task = vm.ReconfigVM_Task(spec)
    wait_for_task(task)


def apply_host_ntp(host, ntp_servers, restart=True):
    """对单个host对象配置NTP并启动ntpd。"""
    dt_system = host.configManager.dateTimeSystem
    ntp_config = vim.host.NtpConfig(server=ntp_servers)
    dt_config = vim.host.DateTimeConfig(ntpConfig=ntp_config)
    dt_system.UpdateDateTimeConfig(dt_config)

    service_system = host.configManager.serviceSystem
    service_system.UpdateServicePolicy(id="ntpd", policy="on")

    if restart:
        svc_list = service_system.serviceInfo.service
        ntpd = next((s for s in svc_list if s.key == "ntpd"), None)
        if ntpd and ntpd.running:
            service_system.RestartService(id="ntpd")
        else:
            service_system.StartService(id="ntpd")


_NTP_EPOCH_DELTA = 2208988800  # NTP纪元(1900-01-01)到Unix纪元(1970-01-01)的秒数差


def query_ntp_time(ntp_host, timeout=3, port=123):
    """向NTP服务器发一个标准NTP查询包，返回该服务器当前时间(Unix时间戳，float)。

    不依赖第三方ntplib库，直接用socket发标准NTP client请求包(48字节)。
    """
    request = b"\x1b" + 47 * b"\0"
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
        client.settimeout(timeout)
        client.sendto(request, (ntp_host, port))
        data, _ = client.recvfrom(48)
    if len(data) < 48:
        raise ValueError(f"NTP服务器 {ntp_host} 返回的数据长度不足(收到{len(data)}字节)")
    unpacked = struct.unpack("!12I", data[:48])
    tx_seconds, tx_fraction = unpacked[10], unpacked[11]
    return (tx_seconds + tx_fraction / 2 ** 32) - _NTP_EPOCH_DELTA


def get_host_time_diff_rows(si, ntp_reference, hosts_filter=None):
    """检测所有ESXi主机时间与参考NTP服务器(ntp_reference)的时间差，单位秒。

    diff_seconds为正表示主机时间比参考服务器快，为负表示慢。
    参考时间只在开头查询一次NTP服务器，之后用本机单调时钟(time.monotonic)推算
    "此刻参考服务器应该是几点"，避免对生产NTP服务器发起大量并发查询。
    """
    ref_unix = query_ntp_time(ntp_reference)
    ref_monotonic = time.monotonic()

    hosts = get_all_objs(si, [vim.HostSystem])
    rows = []
    for host in hosts:
        if hosts_filter and host.name not in hosts_filter:
            continue
        try:
            host_dt = host.configManager.dateTimeSystem.QueryDateTime()
            now_ref = ref_unix + (time.monotonic() - ref_monotonic)
            diff = host_dt.timestamp() - now_ref
            rows.append({
                "host_obj": host,
                "host_name": host.name,
                "host_time_utc": host_dt.strftime("%Y-%m-%d %H:%M:%S UTC"),
                "diff_seconds": diff,
                "error": "",
            })
        except Exception as e:
            rows.append({
                "host_obj": host, "host_name": host.name,
                "host_time_utc": "", "diff_seconds": None, "error": str(e),
            })
    return rows


# ---------------------------------------------------------------------------
# 功能一：排查所有VM的时间同步设置（CLI用，内部调用上面的 get_vm_sync_rows）
# ---------------------------------------------------------------------------

def check_vm_time_sync(si, output_csv=None):
    vms = get_all_objs(si, [vim.VirtualMachine])
    rows = []

    for vm in vms:
        try:
            cfg = vm.config
            summary = vm.summary
            if cfg is None:
                continue

            guest = summary.guest
            tools_status = str(guest.toolsStatus) if guest else "unknown"
            tools_running = str(guest.toolsRunningStatus) if guest else "unknown"

            sync_info = evaluate_vm_time_sync(cfg)

            host_name = vm.runtime.host.name if vm.runtime.host else "N/A"

            rows.append({
                "vm_name": vm.name,
                "power_state": str(summary.runtime.powerState),
                "esxi_host": host_name,
                "guest_full_name": summary.config.guestFullName if summary.config else "",
                "tools_status": tools_status,
                "tools_running": tools_running,
                "sync_time_with_host": sync_info["sync_time_with_host"],
                "sync_legacy_flag": sync_info["sync_legacy_flag"],
                "sync_allowed_flag": sync_info["sync_allowed_flag"],
                "error": "",
            })
        except Exception as e:
            rows.append({
                "vm_name": vm.name, "power_state": "", "esxi_host": "",
                "guest_full_name": "", "tools_status": "", "tools_running": "",
                "sync_time_with_host": "", "sync_legacy_flag": "", "sync_allowed_flag": "",
                "error": str(e),
            })

    sync_on = [r for r in rows if r.get("sync_time_with_host") is True]
    sync_off = [r for r in rows if r.get("sync_time_with_host") is False]
    unknown = [r for r in rows
               if r.get("sync_time_with_host") not in (True, False)]

    print(f"\n共扫描 {len(rows)} 台虚拟机")
    print(f"  开启 '与主机同步时间' : {len(sync_on)} 台  <== 修正ESXi时间前重点关注")
    print(f"  未开启                : {len(sync_off)} 台")
    print(f"  无法判断/无Tools信息   : {len(unknown)} 台\n")

    if sync_on:
        print("以下虚拟机开启了 VMware Tools 与宿主机的时间同步，修正ESXi时间会直接改变这些VM的时间：")
        for r in sorted(sync_on, key=lambda x: x["esxi_host"]):
            print(f"  - {r['vm_name']:<32} 主机:{r['esxi_host']:<18} 电源:{r['power_state']}")

    if unknown:
        print("\n以下虚拟机无法确认同步状态（可能未安装/未运行VMware Tools，建议单独确认，"
              "很多Windows VM即使Tools同步关闭也可能有自己的w32tm/域时间同步）：")
        for r in unknown:
            print(f"  - {r['vm_name']:<32} tools_status:{r['tools_status']}")

    if output_csv:
        fieldnames = ["vm_name", "power_state", "esxi_host", "guest_full_name",
                      "tools_status", "tools_running", "sync_time_with_host",
                      "sync_legacy_flag", "sync_allowed_flag", "error"]
        with open(output_csv, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        print(f"\n详细结果已导出: {output_csv}")

    return rows


def _reconnect_and_refetch(vcenter, user, password, vim_type, wanted_names):
    """vCenter session过期(NotAuthenticated)时自动重新登录，并按name把对象重新找回来。

    批量操作(几百台VM/主机)耗时较长，很容易超过vCenter的session空闲超时时间，
    导致操作到一半直接报NotAuthenticated、前功尽弃。这里在遇到这个错误时
    自动重连一次并继续，而不是让整个批量任务半途而废。
    重连后旧的managed object引用(跟旧session绑定)会失效，所以要用新session
    重新按名字查一遍对象。
    """
    if not (vcenter and user and password):
        raise RuntimeError("vCenter会话失效(NotAuthenticated)，且未提供重连所需的凭据，"
                            "请重新运行/重新点击连接")
    print("[WARN] 检测到vCenter会话失效(NotAuthenticated)，尝试自动重新登录...")
    new_si = connect_vcenter(vcenter, user, password)
    objs = get_all_objs(new_si, vim_type)
    name_to_obj = {o.name: o for o in objs if o.name in wanted_names}
    print("[OK] 重新登录成功，继续处理剩余项。")
    return new_si, name_to_obj


# ---------------------------------------------------------------------------
# 功能二：批量取消VM的"与主机同步时间"
# ---------------------------------------------------------------------------

def disable_vm_time_sync(si, vm_names=None, confirm=False, dry_run=True,
                          vcenter=None, user=None, password=None):
    """
    将VM的 tools.syncTimeWithHost 设为 False。
    默认(dry_run=True)只打印将要修改的VM清单，不实际执行。
    必须同时传 confirm=True 且 dry_run=False 才会真正下发修改。

    传入 vcenter/user/password 后，若批量执行过程中session过期(常见于
    几百台VM的大批量场景耗时超过session空闲超时)，会自动重新登录并继续，
    不需要重跑整个命令。
    """
    vms = get_all_objs(si, [vim.VirtualMachine])
    targets = []
    matched_names = set()

    for vm in vms:
        cfg = vm.config
        if cfg is None:
            continue
        if evaluate_vm_time_sync(cfg)["sync_time_with_host"] is not True:
            continue
        if vm_names and vm.name not in vm_names:
            continue
        targets.append(vm)
        if vm_names:
            matched_names.add(vm.name)

    if vm_names:
        unmatched = set(vm_names) - matched_names
        if unmatched:
            print(f"警告: 以下 --vms 参数未匹配到任何'已开启同步'的VM，请检查名称是否打错: "
                  f"{', '.join(sorted(unmatched))}")

    if not targets:
        print("没有找到需要处理的VM（可能已经全部关闭同步，或 --vms 过滤后为空）")
        return []

    print(f"共找到 {len(targets)} 台开启了'与主机同步时间'的VM：")
    for vm in targets:
        host_name = vm.runtime.host.name if vm.runtime.host else "N/A"
        print(f"  - {vm.name:<32} 主机:{host_name:<18} 电源:{vm.runtime.powerState}")

    if dry_run or not confirm:
        print("\n[DRY-RUN] 以上是将要修改的VM清单，未做任何实际改动。")
        print("确认无误后加上 --confirm 参数重新运行以真正执行修改。")
        return targets

    print("\n开始执行修改...")
    results = []
    target_names = [vm.name for vm in targets]
    name_to_vm = {vm.name: vm for vm in targets}

    for name in target_names:
        vm = name_to_vm.get(name)
        try:
            if vm is None:
                raise RuntimeError("未能找到该VM(可能是重连后被删除/改名)")
            apply_vm_sync(vm, False)
            print(f"[OK]     {name}: 已关闭与主机的时间同步")
            results.append((name, "OK"))
        except vim.fault.NotAuthenticated:
            try:
                _, name_to_vm = _reconnect_and_refetch(
                    vcenter, user, password, [vim.VirtualMachine], target_names)
                vm = name_to_vm.get(name)
                if vm is None:
                    raise RuntimeError("重连后仍未找到该VM")
                apply_vm_sync(vm, False)
                print(f"[OK]     {name}: 已关闭与主机的时间同步(会话重连后重试成功)")
                results.append((name, "OK"))
            except Exception as e2:
                print(f"[FAILED] {name}: 会话重连后仍失败: {e2}")
                results.append((name, f"FAILED: {e2}"))
        except Exception as e:
            print(f"[FAILED] {name}: {e}")
            results.append((name, f"FAILED: {e}"))

    ok_count = sum(1 for r in results if r[1] == "OK")
    print(f"\n完成，共处理 {len(results)} 台，成功 {ok_count} 台，失败 {len(results) - ok_count} 台")
    return results


# ---------------------------------------------------------------------------
# 功能三：批量配置 ESXi NTP
# ---------------------------------------------------------------------------

def set_esxi_ntp(si, ntp_servers, hosts_filter=None, restart_service=True,
                  confirm=False, dry_run=True, vcenter=None, user=None, password=None):
    """
    批量给ESXi主机配置NTP服务器并启动ntpd。
    默认(dry_run=True)只打印将要修改的主机清单，不实际执行。
    必须同时传 confirm=True 且 dry_run=False 才会真正下发修改，
    避免命令行手滑漏填 --hosts/--ntp 时误改全部生产主机的时间源。

    传入 vcenter/user/password 后，若批量执行过程中session过期会自动重新登录并继续。
    """
    hosts = get_all_objs(si, [vim.HostSystem])
    targets = []
    matched_names = set()

    for host in hosts:
        if hosts_filter and host.name not in hosts_filter:
            continue
        targets.append(host)
        if hosts_filter:
            matched_names.add(host.name)

    if hosts_filter:
        unmatched = set(hosts_filter) - matched_names
        if unmatched:
            print(f"警告: 以下 --hosts 参数未匹配到任何主机，请检查名称是否打错: "
                  f"{', '.join(sorted(unmatched))}")

    if not targets:
        print("没有找到需要处理的主机（--hosts 过滤后为空）")
        return []

    print(f"共找到 {len(targets)} 台主机，将配置NTP为 {ntp_servers}，"
          f"{'并重启ntpd' if restart_service else '不重启ntpd，仅写配置'}：")
    for host in targets:
        print(f"  - {host.name}")

    if dry_run or not confirm:
        print("\n[DRY-RUN] 以上是将要修改的主机清单，未做任何实际改动。")
        print("确认无误后加上 --confirm 参数重新运行以真正执行修改。")
        return targets

    print("\n开始执行修改...")
    results = []
    target_names = [host.name for host in targets]
    name_to_host = {host.name: host for host in targets}

    def _do_apply(host):
        current_cfg = host.configManager.dateTimeSystem.dateTimeInfo.ntpConfig
        current_servers = list(current_cfg.server) if current_cfg else []
        apply_host_ntp(host, ntp_servers, restart=restart_service)
        return current_servers

    for name in target_names:
        host = name_to_host.get(name)
        try:
            if host is None:
                raise RuntimeError("未能找到该主机(可能是重连后被删除/改名)")
            current_servers = _do_apply(host)
            results.append((name, "OK", current_servers, ntp_servers))
            print(f"[OK]     {name}: {current_servers} -> {ntp_servers}，ntpd已启动并设为开机自启")
        except vim.fault.NotAuthenticated:
            try:
                _, name_to_host = _reconnect_and_refetch(
                    vcenter, user, password, [vim.HostSystem], target_names)
                host = name_to_host.get(name)
                if host is None:
                    raise RuntimeError("重连后仍未找到该主机")
                current_servers = _do_apply(host)
                results.append((name, "OK", current_servers, ntp_servers))
                print(f"[OK]     {name}: {current_servers} -> {ntp_servers}，"
                      f"ntpd已启动并设为开机自启(会话重连后重试成功)")
            except Exception as e2:
                results.append((name, f"FAILED: {e2}", None, None))
                print(f"[FAILED] {name}: 会话重连后仍失败: {e2}")
        except Exception as e:
            results.append((name, f"FAILED: {e}", None, None))
            print(f"[FAILED] {name}: {e}")

    ok_count = sum(1 for r in results if r[1] == "OK")
    print(f"\n完成，共处理 {len(results)} 台主机，成功 {ok_count} 台，失败 {len(results) - ok_count} 台")
    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="vCenter VM时间同步排查 / ESXi NTP批量配置")
    parser.add_argument("--vcenter", required=True, help="vCenter 地址")
    parser.add_argument("--user", required=True, help="vCenter 用户名")
    parser.add_argument("--password", help="vCenter 密码（不填则交互输入，更安全）")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("check-vm-sync", help="排查所有VM的'与主机同步时间'设置")
    p1.add_argument("--csv", default="vm_time_sync_report.csv", help="导出CSV文件路径")

    p2 = sub.add_parser("disable-vm-sync", help="批量取消VM的'与主机同步时间'")
    p2.add_argument("--vms", nargs="+", help="仅对指定VM名称生效（默认对所有开启同步的VM生效）")
    p2.add_argument("--confirm", action="store_true",
                     help="真正执行修改；不加此参数只会打印将要修改的清单(dry-run)")

    p3 = sub.add_parser("set-ntp", help="批量配置ESXi主机NTP服务器")
    p3.add_argument("--ntp", nargs="+", required=True, help="NTP服务器地址，可填多个（填你自己的NTP服务器）")
    p3.add_argument("--hosts", nargs="+", help="仅对指定主机名生效（默认对全部主机生效）")
    p3.add_argument("--no-restart", action="store_true", help="不重启ntpd服务，仅写配置")
    p3.add_argument("--confirm", action="store_true",
                     help="真正执行修改；不加此参数只会打印将要修改的主机清单(dry-run)")

    args = parser.parse_args()
    pwd = args.password or getpass.getpass(f"{args.user}@{args.vcenter} 密码: ")
    try:
        si = connect_vcenter(args.vcenter, args.user, pwd)
    except Exception as e:
        print(f"[FAILED] 连接vCenter失败: {e}")
        sys.exit(1)

    if args.cmd == "check-vm-sync":
        check_vm_time_sync(si, output_csv=args.csv)
    elif args.cmd == "disable-vm-sync":
        disable_vm_time_sync(si, vm_names=args.vms, confirm=args.confirm, dry_run=not args.confirm,
                              vcenter=args.vcenter, user=args.user, password=pwd)
    elif args.cmd == "set-ntp":
        set_esxi_ntp(si, args.ntp, hosts_filter=args.hosts, restart_service=not args.no_restart,
                     confirm=args.confirm, dry_run=not args.confirm,
                     vcenter=args.vcenter, user=args.user, password=pwd)


if __name__ == "__main__":
    main()
