#!/usr/bin/env python3
"""
vc_time_gui.py
vCenter 时间同步排查 / ESXi NTP 批量配置 —— 图形界面

依赖：
    pip install pyvmomi
    (tkinter 通常随Python自带；如果系统提示没有tkinter，Ubuntu/Debian下: sudo apt install python3-tk)

运行：
    python3 vc_time_gui.py

注意：本文件需要和 vc_time_tool.py 放在同一目录下，GUI直接复用其中的底层函数。
"""

import queue
import ssl
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from pyVim.connect import SmartConnect, Disconnect
from pyVmomi import vim

import vc_time_tool as core  # 复用之前写的底层函数


class VcTimeGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("vCenter 时间同步工具")
        self.geometry("980x680")

        self.si = None  # vCenter连接session
        self._vc_host = None  # 保存连接信息，供批量操作中session过期时自动重连
        self._vc_user = None
        self._vc_pwd = None
        self.log_queue = queue.Queue()
        self.ui_queue = queue.Queue()  # 后台线程 -> 主线程 的Tkinter控件操作队列

        self.vm_rows = []     # 最近一次扫描到的VM数据
        self.host_rows = []   # 最近一次扫描到的Host数据

        self._build_connect_bar()
        self._build_notebook()
        self._build_log_area()

        self.after(150, self._drain_queues)

    # -------------------------------------------------------------------
    # 顶部连接栏
    # -------------------------------------------------------------------
    def _build_connect_bar(self):
        frame = ttk.LabelFrame(self, text="vCenter 连接")
        frame.pack(fill="x", padx=8, pady=6)

        ttk.Label(frame, text="vCenter 地址:").grid(row=0, column=0, padx=4, pady=4, sticky="e")
        self.ent_vc = ttk.Entry(frame, width=20)
        self.ent_vc.grid(row=0, column=1, padx=4, pady=4)

        ttk.Label(frame, text="用户名:").grid(row=0, column=2, padx=4, pady=4, sticky="e")
        self.ent_user = ttk.Entry(frame, width=25)
        self.ent_user.grid(row=0, column=3, padx=4, pady=4)

        ttk.Label(frame, text="密码:").grid(row=0, column=4, padx=4, pady=4, sticky="e")
        self.ent_pwd = ttk.Entry(frame, width=18, show="*")
        self.ent_pwd.grid(row=0, column=5, padx=4, pady=4)

        self.btn_connect = ttk.Button(frame, text="连接", command=self.on_connect)
        self.btn_connect.grid(row=0, column=6, padx=8, pady=4)

        self.lbl_status = ttk.Label(frame, text="未连接", foreground="red")
        self.lbl_status.grid(row=0, column=7, padx=8, pady=4)

    # -------------------------------------------------------------------
    # Tab: VM同步排查 / ESXi NTP配置
    # -------------------------------------------------------------------
    def _build_notebook(self):
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=8, pady=4)

        self._build_vm_tab()
        self._build_host_tab()

    def _build_vm_tab(self):
        tab = ttk.Frame(self.nb)
        self.nb.add(tab, text="VM时间同步排查")

        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=4)
        ttk.Button(bar, text="扫描所有VM", command=self.on_scan_vms).pack(side="left", padx=4)
        ttk.Button(bar, text="全选(仅开启同步)", command=self.on_select_synced_vms).pack(side="left", padx=4)
        ttk.Button(bar, text="取消全选", command=lambda: self._toggle_all(self.vm_tree, False)).pack(side="left", padx=4)
        ttk.Button(bar, text="导出CSV", command=self.on_export_vm_csv).pack(side="left", padx=4)
        ttk.Button(bar, text="关闭勾选VM的同步", command=self.on_disable_selected_vms).pack(side="left", padx=12)

        cols = ("sel", "vm_name", "esxi_host", "power_state", "sync")
        self.vm_tree = ttk.Treeview(tab, columns=cols, show="headings", height=18)
        headers = {"sel": "选择", "vm_name": "虚拟机名称", "esxi_host": "所在ESXi主机",
                   "power_state": "电源状态", "sync": "与主机同步时间"}
        widths = {"sel": 50, "vm_name": 260, "esxi_host": 180, "power_state": 100, "sync": 140}
        for c in cols:
            self.vm_tree.heading(c, text=headers[c])
            self.vm_tree.column(c, width=widths[c], anchor="center" if c != "vm_name" else "w")
        self.vm_tree.pack(fill="both", expand=True, padx=4, pady=4)
        self.vm_tree.bind("<Button-1>", lambda e: self._on_tree_click(e, self.vm_tree))
        self.vm_tree.tag_configure("synced", background="#3a2a2a")

    def _build_host_tab(self):
        tab = ttk.Frame(self.nb)
        self.nb.add(tab, text="ESXi NTP 配置")

        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=4)
        ttk.Button(bar, text="扫描所有主机", command=self.on_scan_hosts).pack(side="left", padx=4)
        ttk.Button(bar, text="全选", command=lambda: self._toggle_all(self.host_tree, True)).pack(side="left", padx=4)
        ttk.Button(bar, text="取消全选", command=lambda: self._toggle_all(self.host_tree, False)).pack(side="left", padx=4)

        ttk.Label(bar, text="  目标NTP服务器(逗号分隔):").pack(side="left", padx=(20, 4))
        self.ent_ntp = ttk.Entry(bar, width=25)
        self.ent_ntp.pack(side="left")

        self.var_restart = tk.BooleanVar(value=True)
        ttk.Checkbutton(bar, text="应用后重启ntpd", variable=self.var_restart).pack(side="left", padx=8)

        ttk.Button(bar, text="应用到勾选主机", command=self.on_apply_ntp).pack(side="left", padx=12)

        bar2 = ttk.Frame(tab)
        bar2.pack(fill="x", pady=(0, 4))
        ttk.Label(bar2, text="参考时间源(检测时间差用):").pack(side="left", padx=(4, 4))
        self.ent_ref_ntp = ttk.Entry(bar2, width=25)
        self.ent_ref_ntp.pack(side="left")
        ttk.Button(bar2, text="检测所有主机时间差", command=self.on_check_time_diff).pack(side="left", padx=12)

        cols = ("sel", "host_name", "current_ntp", "ntpd_running", "ntpd_policy", "conn_state", "time_diff")
        self.host_tree = ttk.Treeview(tab, columns=cols, show="headings", height=18)
        headers = {"sel": "选择", "host_name": "主机", "current_ntp": "当前NTP",
                   "ntpd_running": "ntpd运行中", "ntpd_policy": "启动策略", "conn_state": "连接状态",
                   "time_diff": "与参考源时间差(秒)"}
        widths = {"sel": 50, "host_name": 180, "current_ntp": 220, "ntpd_running": 90,
                  "ntpd_policy": 90, "conn_state": 100, "time_diff": 140}
        for c in cols:
            self.host_tree.heading(c, text=headers[c])
            self.host_tree.column(c, width=widths[c], anchor="center" if c != "host_name" else "w")
        self.host_tree.pack(fill="both", expand=True, padx=4, pady=4)
        self.host_tree.bind("<Button-1>", lambda e: self._on_tree_click(e, self.host_tree))
        self.host_tree.tag_configure("drift", background="#3a2a2a")

    def _build_log_area(self):
        frame = ttk.LabelFrame(self, text="日志")
        frame.pack(fill="both", padx=8, pady=6)
        self.txt_log = tk.Text(frame, height=10, state="disabled", bg="#1e1e1e", fg="#d4d4d4")
        self.txt_log.pack(fill="both", expand=True, padx=4, pady=4)

    # -------------------------------------------------------------------
    # 通用: checkbox列点击切换 / 全选/反选
    # -------------------------------------------------------------------
    def _on_tree_click(self, event, tree):
        region = tree.identify("region", event.x, event.y)
        if region != "cell":
            return
        col = tree.identify_column(event.x)
        row = tree.identify_row(event.y)
        if not row or col != "#1":  # 第一列 = sel
            return
        current = tree.set(row, "sel")
        tree.set(row, "sel", "" if current == "☑" else "☑")

    def _toggle_all(self, tree, checked, only_true_sync=False):
        mark = "☑" if checked else ""
        for row in tree.get_children():
            if only_true_sync and tree.set(row, "sync") != "True":
                continue
            tree.set(row, "sel", mark)

    def _get_selected_indices(self, tree):
        return [i for i, row in enumerate(tree.get_children()) if tree.set(row, "sel") == "☑"]

    # -------------------------------------------------------------------
    # 日志
    # -------------------------------------------------------------------
    def log(self, msg):
        self.log_queue.put(msg)

    def call_on_main(self, fn, *args, **kwargs):
        """供后台线程调用：把需要操作Tkinter控件的回调丢回主线程执行。

        Tkinter控件不是线程安全的，后台worker线程不能直接调用 self.xxx_tree.insert /
        self.lbl_status.config 等方法，必须经由这个队列转到主线程的事件循环里执行。
        """
        self.ui_queue.put((fn, args, kwargs))

    def _drain_queues(self):
        while not self.log_queue.empty():
            msg = self.log_queue.get_nowait()
            self.txt_log.configure(state="normal")
            self.txt_log.insert("end", msg + "\n")
            self.txt_log.see("end")
            self.txt_log.configure(state="disabled")
        while not self.ui_queue.empty():
            fn, args, kwargs = self.ui_queue.get_nowait()
            fn(*args, **kwargs)
        self.after(150, self._drain_queues)

    def run_in_thread(self, fn, *args):
        threading.Thread(target=fn, args=args, daemon=True).start()

    # -------------------------------------------------------------------
    # 连接
    # -------------------------------------------------------------------
    def on_connect(self):
        vc, user, pwd = self.ent_vc.get().strip(), self.ent_user.get().strip(), self.ent_pwd.get()
        if not vc or not user or not pwd:
            messagebox.showwarning("提示", "请填写vCenter地址、用户名和密码")
            return
        self.btn_connect.config(state="disabled")
        self.lbl_status.config(text="连接中...", foreground="orange")
        self.run_in_thread(self._connect_worker, vc, user, pwd)

    def _connect_worker(self, vc, user, pwd):
        try:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            si = SmartConnect(host=vc, user=user, pwd=pwd, port=443, sslContext=context)
            self.si = si
            self._vc_host, self._vc_user, self._vc_pwd = vc, user, pwd
            self.log(f"[OK] 已连接到 {vc}")
            self.call_on_main(self.lbl_status.config, text=f"已连接: {vc}", foreground="green")
        except Exception as e:
            self.si = None
            self.log(f"[FAILED] 连接失败: {e}")
            self.call_on_main(self.lbl_status.config, text="连接失败", foreground="red")
            self.call_on_main(messagebox.showerror, "连接失败", str(e))
        finally:
            self.call_on_main(self.btn_connect.config, state="normal")

    def _require_connection(self):
        if self.si is None:
            messagebox.showwarning("提示", "请先连接vCenter")
            return False
        return True

    def _reconnect_si(self):
        """批量操作中途session过期(NotAuthenticated)时自动重新登录一次。

        几百台VM/主机的批量操作耗时较长，容易超过vCenter的session空闲超时；
        这里用连接时保存的凭据自动重连，避免大批量任务半途而废、必须重跑。
        """
        if not (self._vc_host and self._vc_user and self._vc_pwd):
            raise RuntimeError("会话已失效，且没有保存的登录信息可用于自动重连，请重新点击'连接'")
        self.log("[WARN] 检测到vCenter会话失效(NotAuthenticated)，尝试自动重新登录...")
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        self.si = SmartConnect(host=self._vc_host, user=self._vc_user, pwd=self._vc_pwd,
                                port=443, sslContext=context)
        self.log("[OK] 重新登录成功，继续处理剩余项。")

    # -------------------------------------------------------------------
    # VM Tab 逻辑
    # -------------------------------------------------------------------
    def on_scan_vms(self):
        if not self._require_connection():
            return
        self.log("开始扫描VM...")
        self.run_in_thread(self._scan_vms_worker)

    def _scan_vms_worker(self):
        try:
            rows = core.get_vm_sync_rows(self.si)
            self.call_on_main(self._populate_vm_tree, rows)
        except Exception as e:
            self.log(f"[FAILED] 扫描VM失败: {e}")

    def _populate_vm_tree(self, rows):
        """在主线程里刷新VM表格，避免后台线程直接操作Tkinter控件。"""
        self.vm_rows = rows
        for row in self.vm_tree.get_children():
            self.vm_tree.delete(row)
        for r in rows:
            tag = ("synced",) if r["sync_time_with_host"] is True else ()
            self.vm_tree.insert("", "end", values=(
                "", r["vm_name"], r["esxi_host"], r["power_state"], r["sync_time_with_host"]
            ), tags=tag)
        synced_count = sum(1 for r in rows if r["sync_time_with_host"] is True)
        self.log(f"[OK] 共扫描 {len(rows)} 台VM，其中 {synced_count} 台开启了与主机同步时间")

    def on_select_synced_vms(self):
        self._toggle_all(self.vm_tree, True, only_true_sync=True)

    def on_export_vm_csv(self):
        if not self.vm_rows:
            messagebox.showinfo("提示", "请先扫描VM")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", initialfile="vm_time_sync_report.csv")
        if not path:
            return
        import csv
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(["vm_name", "esxi_host", "power_state", "sync_time_with_host"])
            for r in self.vm_rows:
                writer.writerow([r["vm_name"], r["esxi_host"], r["power_state"], r["sync_time_with_host"]])
        self.log(f"[OK] 已导出: {path}")

    def on_disable_selected_vms(self):
        if not self._require_connection():
            return
        indices = self._get_selected_indices(self.vm_tree)
        if not indices:
            messagebox.showinfo("提示", "请先在表格里勾选要处理的VM")
            return
        names = [self.vm_rows[i]["vm_name"] for i in indices]
        if not messagebox.askyesno("确认", f"将对以下 {len(names)} 台VM关闭'与主机同步时间'，确认执行？\n\n" + "\n".join(names[:20]) +
                                    ("\n..." if len(names) > 20 else "")):
            return
        self.run_in_thread(self._disable_vms_worker, indices)

    def _disable_vms_worker(self, indices):
        for i in indices:
            r = self.vm_rows[i]
            try:
                core.apply_vm_sync(r["vm_obj"], False)
                self.log(f"[OK] {r['vm_name']}: 已关闭与主机的时间同步")
            except vim.fault.NotAuthenticated:
                try:
                    self._reconnect_si()
                    fresh = next((v for v in core.get_all_objs(self.si, [vim.VirtualMachine])
                                  if v.name == r["vm_name"]), None)
                    if fresh is None:
                        raise RuntimeError("重连后未能重新找到该VM")
                    r["vm_obj"] = fresh
                    core.apply_vm_sync(fresh, False)
                    self.log(f"[OK] {r['vm_name']}: 已关闭与主机的时间同步(会话重连后重试成功)")
                except Exception as e2:
                    self.log(f"[FAILED] {r['vm_name']}: 会话重连后仍失败: {e2}")
            except Exception as e:
                self.log(f"[FAILED] {r['vm_name']}: {e}")
        self.log("批量操作完成，建议重新点击'扫描所有VM'刷新状态。")

    # -------------------------------------------------------------------
    # Host Tab 逻辑
    # -------------------------------------------------------------------
    def on_scan_hosts(self):
        if not self._require_connection():
            return
        self.log("开始扫描ESXi主机...")
        self.run_in_thread(self._scan_hosts_worker)

    def _scan_hosts_worker(self):
        try:
            rows = core.get_host_ntp_rows(self.si)
            self.call_on_main(self._populate_host_tree, rows)
        except Exception as e:
            self.log(f"[FAILED] 扫描主机失败: {e}")

    def _populate_host_tree(self, rows):
        """在主线程里刷新主机表格，避免后台线程直接操作Tkinter控件。"""
        self.host_rows = rows
        for row in self.host_tree.get_children():
            self.host_tree.delete(row)
        for r in rows:
            self.host_tree.insert("", "end", values=(
                "", r["host_name"], r["current_ntp"], r["ntpd_running"], r["ntpd_policy"], r["connection_state"], ""
            ))
        self.log(f"[OK] 共扫描 {len(rows)} 台主机")

    def on_apply_ntp(self):
        if not self._require_connection():
            return
        indices = self._get_selected_indices(self.host_tree)
        if not indices:
            messagebox.showinfo("提示", "请先在表格里勾选要处理的主机")
            return
        ntp_text = self.ent_ntp.get().strip()
        if not ntp_text:
            messagebox.showwarning("提示", "请填写NTP服务器地址")
            return
        ntp_servers = [s.strip() for s in ntp_text.split(",") if s.strip()]
        names = [self.host_rows[i]["host_name"] for i in indices]
        if not messagebox.askyesno("确认", f"将对以下 {len(names)} 台主机配置NTP为 {ntp_servers} 并"
                                    f"{'重启' if self.var_restart.get() else '不重启'}ntpd，确认执行？\n\n" +
                                    "\n".join(names)):
            return
        self.run_in_thread(self._apply_ntp_worker, indices, ntp_servers)

    def _apply_ntp_worker(self, indices, ntp_servers):
        restart = self.var_restart.get()
        for i in indices:
            r = self.host_rows[i]
            try:
                core.apply_host_ntp(r["host_obj"], ntp_servers, restart=restart)
                self.log(f"[OK] {r['host_name']}: NTP已设为 {ntp_servers}")
            except vim.fault.NotAuthenticated:
                try:
                    self._reconnect_si()
                    fresh = next((h for h in core.get_all_objs(self.si, [vim.HostSystem])
                                  if h.name == r["host_name"]), None)
                    if fresh is None:
                        raise RuntimeError("重连后未能重新找到该主机")
                    r["host_obj"] = fresh
                    core.apply_host_ntp(fresh, ntp_servers, restart=restart)
                    self.log(f"[OK] {r['host_name']}: NTP已设为 {ntp_servers}(会话重连后重试成功)")
                except Exception as e2:
                    self.log(f"[FAILED] {r['host_name']}: 会话重连后仍失败: {e2}")
            except Exception as e:
                self.log(f"[FAILED] {r['host_name']}: {e}")
        self.log("批量操作完成，建议重新点击'扫描所有主机'刷新状态。")

    # 与参考NTP源相差超过这个秒数就标红提醒
    TIME_DIFF_DRIFT_THRESHOLD = 5.0

    def on_check_time_diff(self):
        if not self._require_connection():
            return
        if not self.host_rows:
            messagebox.showinfo("提示", "请先点击'扫描所有主机'")
            return
        ref_server = self.ent_ref_ntp.get().strip()
        if not ref_server:
            messagebox.showwarning("提示", "请填写用于比对的参考时间源地址")
            return
        self.log(f"开始检测所有主机与 {ref_server} 的时间差...")
        self.run_in_thread(self._check_time_diff_worker, ref_server)

    def _check_time_diff_worker(self, ref_server):
        try:
            rows = core.get_host_time_diff_rows(self.si, ref_server)
            self.call_on_main(self._populate_time_diff, rows)
        except Exception as e:
            self.log(f"[FAILED] 检测时间差失败（参考时间源 {ref_server} 是否可达/开放UDP 123端口？）: {e}")

    def _populate_time_diff(self, rows):
        """在主线程里把时间差结果写回主机表格已有的行，不用重新扫描。"""
        diff_by_name = {r["host_name"]: r for r in rows}
        for item_id in self.host_tree.get_children():
            host_name = self.host_tree.set(item_id, "host_name")
            r = diff_by_name.get(host_name)
            if r is None:
                continue
            if r["error"]:
                self.host_tree.set(item_id, "time_diff", f"失败: {r['error']}")
                continue
            diff = r["diff_seconds"]
            self.host_tree.set(item_id, "time_diff", f"{diff:+.1f}")
            tags = () if abs(diff) <= self.TIME_DIFF_DRIFT_THRESHOLD else ("drift",)
            self.host_tree.item(item_id, tags=tags)

        ok_rows = [r for r in rows if not r["error"]]
        fail_count = len(rows) - len(ok_rows)
        if ok_rows:
            max_abs = max(abs(r["diff_seconds"]) for r in ok_rows)
            self.log(f"[OK] 时间差检测完成，共 {len(rows)} 台主机，{fail_count} 台失败，最大偏差 {max_abs:+.1f} 秒")
        else:
            self.log("[FAILED] 所有主机时间差检测均失败")

    def on_close(self):
        if self.si:
            try:
                Disconnect(self.si)
            except Exception:
                pass
        self.destroy()


if __name__ == "__main__":
    app = VcTimeGUI()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()
