import tkinter as tk
from tkinter import ttk
from tkinter import filedialog, messagebox
from pyVim.connect import SmartConnect, Disconnect
from pyVmomi import vim
import ssl
import time
from datetime import datetime
import json
import threading
import queue

# 创建主窗口
root = tk.Tk()
root.title("快照管理工具 1.0")
root.geometry("900x350")  # 增加窗口高度

# 记录登录信息的文件
config_file = "vcenter_config.json"

# 创建一个线程安全的队列
log_queue = queue.Queue()

def save_credentials(ip, username, password):
    """保存多个 vCenter 登录信息到本地文件"""
    try:
        with open(config_file, "r") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {}
    
    data[ip] = {"username": username, "password": password}
    with open(config_file, "w") as f:
        json.dump(data, f, indent=4)

def load_credentials():
    """加载所有 vCenter 登录信息"""
    try:
        with open(config_file, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

# 加载已保存的 vCenter 登录信息
saved_credentials = load_credentials()

# 变量定义
entries = []
vcenter_var = tk.StringVar()
first_ip = None  # 初始化 first_ip

def autofill_credentials(event=None):
    """选择 vCenter IP 后自动填充用户名和密码"""
    ip = vcenter_var.get().strip()
    if ip in saved_credentials:
        entries[0].delete(0, tk.END)
        entries[0].insert(0, ip)
        entries[1].delete(0, tk.END)
        entries[1].insert(0, saved_credentials[ip]["username"])
        entries[2].delete(0, tk.END)
        entries[2].insert(0, saved_credentials[ip]["password"])

# 标签和输入框
labels = ["vCenter IP", "Username", "Password"]

for i, text in enumerate(labels):
    tk.Label(root, text=text, font=("Arial", 10)).place(x=20, y=40 + i * 40)
    entry = tk.Entry(root, width=30)
    entry.place(x=120, y=40 + i * 40)
    entries.append(entry)

# 绑定 IP 输入框的自动填充事件
entries[0].bind("<FocusOut>", autofill_credentials)

# 预填充上次使用的 vCenter 信息
if saved_credentials:
    first_ip = next(iter(saved_credentials.keys()))
    vcenter_var.set(first_ip)
    autofill_credentials()

# vCenter IP 下拉菜单
options = list(saved_credentials.keys()) if saved_credentials else []
vcenter_dropdown = tk.OptionMenu(root, vcenter_var, first_ip if first_ip else "", *options, command=autofill_credentials)
vcenter_dropdown.place(x=280, y=40)

# 工作状态显示区域
status_label = tk.Label(root, text="工作状态", font=("Arial", 10, "bold"))
status_label.place(x=400, y=40)

status_text = tk.Text(root, width=60, height=15, bg="black", fg="green")
status_text.place(x=400, y=40, height=255)

def log_message(message):
    """将日志消息放入队列"""
    log_queue.put(message)

def update_status_text():
    """在主线程中更新状态文本"""
    try:
        while True:
            message = log_queue.get_nowait()
            status_text.insert(tk.END, message + "\n")
            status_text.see(tk.END)
            status_text.update_idletasks()
    except queue.Empty:
        pass
    root.after(100, update_status_text)

def connect_to_vcenter():
    """连接到 vCenter"""
    ip = entries[0].get().strip()
    username = entries[1].get().strip()
    password = entries[2].get().strip()

    save_credentials(ip, username, password)  # 记录多个 vCenter 信息
    log_message(f"🔍 连接信息: IP={ip}, 用户={username}")

    if not ip or not username or not password:
        messagebox.showwarning("警告", "请填写完整的 vCenter 连接信息！")
        return None

    try:
        context = ssl._create_unverified_context()
        si = SmartConnect(host=ip, user=username, pwd=password, sslContext=context)
        log_message(f"✅ 成功连接到 vCenter: {ip}")
        return si
    except vim.fault.InvalidLogin:
        log_message("❌ 连接失败：用户名或密码错误！")
    except Exception as e:
        log_message(f"❌ 连接失败: {str(e)}")
    
    return None

# 定义删除快照函数
def delete_snapshots():
    """删除快照（在 GUI 中运行）"""
    si = connect_to_vcenter()
    if not si:
        return
    content = si.RetrieveContent()
    log_message("🔍 正在获取所有虚拟机...")
    vm_view = content.viewManager.CreateContainerView(
        container=content.rootFolder, type=[vim.VirtualMachine], recursive=True
    )
    try:
        vms = vm_view.view
    finally:
        vm_view.Destroy()
    total_vms = len(vms)
    for i, vm in enumerate(vms, start=1):
        log_message(f"📌 检查虚拟机快照: {vm.name}")
        update_progress((i / total_vms) * 50)
        snapshots = get_snapshots(vm)
        if snapshots:
            to_keep, to_delete = filter_and_manage_snapshots(snapshots)
            log_message(f"✅ 保留的快照: {[snap.name for snap, _ in to_keep]}")
            total = len(to_delete)
            for index, (snap, _) in enumerate(to_delete, start=1):
                log_message(f"🚨 删除快照 ({index}/{total}): {snap.name}")
                task = snap.snapshot.RemoveSnapshot_Task(removeChildren=False)
                while task.info.state not in ["success", "error"]:
                    progress = task.info.progress
                    if progress is not None:
                        log_message(f"📊 删除进度: {progress}%")
                        update_progress(50 + ((index / total) * 50))
                    time.sleep(1)
                if task.info.state == "success":
                    log_message(f"✅ {snap.name} 删除成功")
                else:
                    log_message(f"❌ 删除失败: {task.info.error}")
        else:
            log_message("🔍 未发现快照")
        time.sleep(2)  # 在每次虚拟机操作之间加入2秒延时
    Disconnect(si)
    log_message("✅ 删除快照任务完成！")
    update_progress(100)

# 定义创建快照函数
def create_snapshots():
    """按照 Excel 配置创建快照"""
    global config_file_path
    if not config_file_path:
        messagebox.showwarning("警告", "请先选择配置文件！")
        return
    vm_config = load_vm_config(config_file_path)
    si = connect_to_vcenter()
    if not si:
        return
    content = si.RetrieveContent()
    log_message("🔍 正在获取所有虚拟机...")
    vm_view = content.viewManager.CreateContainerView(
        container=content.rootFolder, type=[vim.VirtualMachine], recursive=True
    )
    try:
        vms = vm_view.view
    finally:
        vm_view.Destroy()
    total_vms = len(vms)
    for i, vm in enumerate(vms, start=1):
        log_message(f"📌 处理虚拟机: {vm.name}")
        update_progress((i / total_vms) * 100)
        if vm.name in vm_config and vm.runtime.powerState == vim.VirtualMachinePowerState.poweredOn:
            snapshot_name = f"Snapshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            include_memory = vm_config[vm.name]['include_memory']
            log_message(f"🚀 正在为 {vm.name} 创建快照: {snapshot_name}")
            try:
                task = vm.CreateSnapshot_Task(name=snapshot_name, description="Automated snapshot", memory=include_memory, quiesce=False)
                while task.info.state not in [vim.TaskInfo.State.success, vim.TaskInfo.State.error]:
                    time.sleep(1)
                if task.info.state == vim.TaskInfo.State.success:
                    log_message(f"✅ {vm.name} 快照创建成功")
                else:
                    log_message(f"❌ {vm.name} 快照创建失败")
            except Exception as e:
                log_message(f"❌ {vm.name} 快照创建失败: {e}")
        else:
            log_message(f"⚠️ {vm.name} 未在配置文件中，或未开机，跳过...")
        time.sleep(2)  # 在每次虚拟机操作之间加入2秒延时
    Disconnect(si)
    log_message("✅ 快照创建任务完成！")
    update_progress(100)

# 使用多线程执行快照操作
def threaded_create_snapshots():
    threading.Thread(target=create_snapshots).start()

# 使用多线程执行删除快照操作
def threaded_delete_snapshots():
    threading.Thread(target=delete_snapshots).start()

# 定义其他辅助函数
def get_snapshots(vm):
    """获取虚拟机的所有快照"""
    snapshots = []
    def traverse_snapshot_tree(snapshot_tree):
        for snapshot in snapshot_tree:
            snapshots.append((snapshot, snapshot.createTime))
            if snapshot.childSnapshotList:
                traverse_snapshot_tree(snapshot.childSnapshotList)
    if vm.snapshot:
        traverse_snapshot_tree(vm.snapshot.rootSnapshotList)
    return snapshots

def filter_and_manage_snapshots(snapshots):
    """筛选快照并保留所需的"""
    today = datetime.now().date()
    snapshot_info = []
    for snap, create_time in snapshots:
        snap_create_time = create_time.replace(tzinfo=None).date()
        snapshot_info.append((snap, snap_create_time))
    snapshots_with_today = [s for s in snapshot_info if s[1] == today]
    snapshots_without_today = [s for s in snapshot_info if s[1] != today]
    snapshots_with_today.sort(key=lambda x: x[1], reverse=True)
    snapshots_without_today.sort(key=lambda x: x[1], reverse=True)
    to_keep = snapshots_with_today[:3] + snapshots_without_today[:2]
    to_delete = snapshots_with_today[3:] + snapshots_without_today[2:]
    return to_keep, to_delete

def update_progress(value):
    progress_var.set(value)
    root.update_idletasks()

def select_config_file():
    """让用户选择 Excel 配置文件"""
    file_path = filedialog.askopenfilename(title="选择配置文件", filetypes=[("Excel Files", "*.xlsx")])
    if file_path:
        global config_file_path
        config_file_path = file_path
        log_message(f"✅ 选择的配置文件: {file_path}")

def load_vm_config(file_path):
    """从 Excel 文件加载虚拟机配置"""
    import openpyxl
    vm_config = {}
    try:
        workbook = openpyxl.load_workbook(file_path)
        sheet = workbook.active
        header = [cell.value for cell in sheet[1]]
        required_columns = ["VM Name", "Include Memory"]
        if not all(col in header for col in required_columns):
            raise ValueError("Excel 文件缺少必要的列: VM Name 和 Include Memory")
        for row in sheet.iter_rows(min_row=2, values_only=True):
            vm_name, include_memory = row
            vm_config[vm_name] = {"include_memory": include_memory}
    except Exception as e:
        log_message(f"❌ 加载配置文件失败: {e}")
    return vm_config

# 按钮
btn_connect = tk.Button(root, text="连接 vCenter", bg="green", fg="white", command=connect_to_vcenter)
btn_connect.place(x=20, y=160, width=100, height=30)

btn_delete = tk.Button(root, text="删除快照", bg="green", fg="white", command=threaded_delete_snapshots)
btn_delete.place(x=20, y=200, width=100, height=30)

tk.Label(root, text="只保留2个最近的快照，删除其他快照", font=("Arial", 9)).place(x=140, y=205)

btn_create = tk.Button(root, text="生成快照", bg="green", fg="white", command=threaded_create_snapshots)
btn_create.place(x=20, y=240, width=100, height=30)

btn_upload = tk.Button(root, text="选择配置文件", bg="green", fg="white", command=select_config_file)
btn_upload.place(x=140, y=240, width=120, height=30)

tk.Label(root, text="根据配置文件决定哪个虚拟机需要做快照，快照是否包含内存", font=("Arial", 9)).place(x=20, y=280)

# 进度条
progress_var = tk.DoubleVar()
progress_bar = tk.ttk.Progressbar(root, variable=progress_var, maximum=100, length=480)
progress_bar.place(x=400, y=320)

# 启动状态文本更新
update_status_text()

# 运行窗口
root.mainloop()