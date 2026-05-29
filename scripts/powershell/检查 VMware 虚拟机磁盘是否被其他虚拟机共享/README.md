# VMware VM Disk Sharing Detection Script (PowerCLI) | VMware 虚拟机磁盘共享检测脚本

This script checks whether the VMDK disks of a specified VM are shared by other VMs in a vSphere environment, helping to determine whether the VM and its disks can be safely deleted.

本脚本用于 vSphere 环境中检查指定虚拟机的磁盘是否被其他虚拟机共享使用，辅助判断该虚拟机及磁盘是否可以安全删除。

## ✅ Features | 功能说明

- Connect to vCenter Server | 连接 vCenter Server
- Retrieve all VMDK paths of a specified VM | 获取指定虚拟机的所有 VMDK 磁盘文件路径
- Scan all VMs to detect shared disk usage | 遍历所有虚拟机，查找是否存在共享使用同一磁盘的情况
- Report whether the VM can be safely deleted | 输出判断是否可以安全删除该虚拟机

## 🔧 Usage | 使用方法

1. Install [VMware PowerCLI](https://developer.vmware.com/powercli/) | 安装 VMware PowerCLI
2. Edit the vCenter login info in the script | 修改脚本中的 vCenter 登录信息
3. Set the target VM name | 修改目标虚拟机名称
4. Run the `.ps1` script in PowerShell | 在 PowerShell 中执行脚本，查看控制台输出

## 🔒 Safety | 安全说明

This script performs **read-only** operations and will not modify any VM, disk, or cluster configuration. Safe to use in production environments.

本脚本只执行只读操作，不会对任何虚拟机、磁盘或集群配置产生影响，可放心在生产环境中使用。

## 📦 Output Example | 输出示例

```
[检查磁盘] [666] 666.vmdk
该磁盘未被其他虚拟机使用。

✅ 所有磁盘仅属于虚拟机 VMname，可以安全删除。
```

## 🧩 Requirements | 适用环境

- vCenter (ESXi 6.5+)
- PowerCLI 12.x or 13.x
