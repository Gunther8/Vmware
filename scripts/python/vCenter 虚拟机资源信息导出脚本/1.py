from pyVim.connect import SmartConnect, Disconnect
from pyVmomi import vim
import ssl
from openpyxl import Workbook
from datetime import datetime

# 禁用 SSL 证书验证
ssl_context = ssl._create_unverified_context()

# vCenter Server 连接信息
vcenter_server = "10.1.1.1"
username = "666@vSphere.local"
password = "123456"

# 获取虚拟机列表（递归）
def get_all_vms(folder):
    vms = []
    for item in folder.childEntity:
        if isinstance(item, vim.VirtualMachine):
            vms.append(item)
        elif isinstance(item, vim.Folder):
            vms.extend(get_all_vms(item))  # 递归处理子文件夹
    return vms

# 获取虚拟机的资源信息
def get_vm_resources(vm):
    cpu_cores = vm.config.hardware.numCPU
    memory_gb = vm.config.hardware.memoryMB / 1024
    disk_capacity_gb = 0
    vm_ips = []

    for device in vm.config.hardware.device:
        if isinstance(device, vim.vm.device.VirtualDisk):
            disk_capacity_gb += device.capacityInKB / (1024 * 1024)

    # 获取虚拟机的 IP 地址
    if vm.guest is not None and vm.guest.net is not None:
        for net in vm.guest.net:
            if net.ipConfig and net.ipConfig.ipAddress:
                # 获取所有非空的 IPv4 地址
                for ip in net.ipConfig.ipAddress:
                    if ":" not in ip.ipAddress:  # 排除 IPv6
                        vm_ips.append(ip.ipAddress)

    # 限制返回的最多两个 IP
    return cpu_cores, memory_gb, disk_capacity_gb, ", ".join(vm_ips[:2])

# 功能：记录开机虚拟机的资源信息到 Excel
def record_vm_resources(si, output_file):
    content = si.RetrieveContent()
    vms = []

    # 获取所有虚拟机（递归）
    print("[INFO] Gathering resource information for all powered-on VMs...")
    for datacenter in content.rootFolder.childEntity:
        if hasattr(datacenter, 'vmFolder'):
            all_vms = get_all_vms(datacenter.vmFolder)
            for vm in all_vms:
                if vm.runtime.powerState == vim.VirtualMachinePowerState.poweredOn:
                    print(f"[INFO] Found powered-on VM: {vm.name}")
                    vms.append(vm)

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "VM Resources"

    # 写入表头
    sheet.append(["VM Name", "CPU Cores", "Memory (GB)", "Disk Capacity (GB)", "IP Addresses"])

    for vm in vms:
        print(f"[INFO] Processing VM: {vm.name}")
        cpu_cores, memory_gb, disk_capacity_gb, vm_ips = get_vm_resources(vm)
        print(f"[INFO] VM: {vm.name}, CPU: {cpu_cores} cores, Memory: {memory_gb:.2f} GB, Disk: {disk_capacity_gb:.2f} GB, IPs: {vm_ips}")
        sheet.append([vm.name, cpu_cores, round(memory_gb, 2), round(disk_capacity_gb, 2), vm_ips])

    # 保存文件
    workbook.save(output_file)
    print(f"[SUCCESS] Resource information saved to {output_file}")

# 主函数
def main():
    try:
        # 连接到 vCenter Server
        print("[INFO] Connecting to vCenter Server...")
        si = SmartConnect(host=vcenter_server, user=username, pwd=password, sslContext=ssl_context)
        print("[SUCCESS] Connected to vCenter Server")

        # 动态生成文件名
        date_str = datetime.now().strftime("%Y%m%d")
        output_file = f"{vcenter_server}内所有开机虚拟机资源情况{date_str}.xlsx"

        # 记录资源信息
        print("[INFO] Recording resource information to Excel...")
        record_vm_resources(si, output_file)

    except Exception as e:
        print(f"[ERROR] {e}")

    finally:
        Disconnect(si)
        print("[INFO] Disconnected from vCenter Server")

if __name__ == "__main__":
    main()
