#!/usr/bin/env python3
"""
vc_time_diag.py
临时诊断脚本：dump单个VM的时间同步相关原始配置。

用于确认 vSphere 新版UI里"与主机同步时间"下的
"在启动和恢复时同步" / "定期同步时间" 两个勾选框，
在你这套vCenter/VMware Tools版本上到底对应哪个API字段/vmx高级选项，
这样才能让 vc_time_tool.py 的扫描逻辑读对字段。

用法：
    python3 vc_time_diag.py --vcenter vcenter.example.com --user administrator@vsphere.local --vm "VM名称"

--vm 填要诊断的VM名称（跟vCenter里显示的完全一致）。
"""

import argparse
import getpass

import vc_time_tool as core
from pyVmomi import vim


def dump_vm(si, vm_name):
    vms = core.get_all_objs(si, [vim.VirtualMachine])
    vm = next((v for v in vms if v.name == vm_name), None)
    if vm is None:
        print(f"未找到名为 [{vm_name}] 的VM，请检查名称是否和vCenter里显示的完全一致（包括大小写/空格）")
        candidates = [v.name for v in vms if vm_name.lower() in v.name.lower()]
        if candidates:
            print("名称里包含关键字的候选VM：")
            for c in candidates[:20]:
                print(f"  - {c}")
        return

    cfg = vm.config
    guest = vm.summary.guest

    print(f"=== {vm_name} ===")
    print(f"硬件版本: {cfg.version}")
    print(f"VMware Tools 版本: {getattr(guest, 'toolsVersion', 'N/A') if guest else 'N/A'}")
    print(f"VMware Tools 状态: {getattr(guest, 'toolsStatus', 'N/A') if guest else 'N/A'}")
    print()

    print("--- cfg.tools (ToolsConfigInfo) 全部字段 ---")
    if cfg.tools is not None:
        for attr in dir(cfg.tools):
            if attr.startswith("_"):
                continue
            try:
                val = getattr(cfg.tools, attr)
            except Exception:
                continue
            if callable(val):
                continue
            print(f"  {attr} = {val!r}")
    else:
        print("  cfg.tools 为 None")
    print()

    print("--- cfg.extraConfig 中 key 包含 'sync' 或 'time' 的项（不区分大小写） ---")
    found = False
    for opt in (cfg.extraConfig or []):
        if "sync" in opt.key.lower() or "time" in opt.key.lower():
            print(f"  {opt.key} = {opt.value!r}")
            found = True
    if not found:
        print("  (extraConfig里没有任何 key 包含 sync/time)")
    print()

    print("--- cfg.extraConfig 全量key列表（如果上面啥都没有，看看有没有拼写不同的相关key） ---")
    all_keys = sorted(opt.key for opt in (cfg.extraConfig or []))
    print(f"  共 {len(all_keys)} 项，全部key：")
    for k in all_keys:
        print(f"  - {k}")


def main():
    parser = argparse.ArgumentParser(description="诊断单个VM的时间同步相关原始配置")
    parser.add_argument("--vcenter", required=True)
    parser.add_argument("--user", required=True)
    parser.add_argument("--password", help="不填则交互输入，更安全")
    parser.add_argument("--vm", required=True, help="要诊断的VM名称")
    args = parser.parse_args()

    pwd = args.password or getpass.getpass(f"{args.user}@{args.vcenter} 密码: ")
    si = core.connect_vcenter(args.vcenter, args.user, pwd)
    dump_vm(si, args.vm)


if __name__ == "__main__":
    main()
