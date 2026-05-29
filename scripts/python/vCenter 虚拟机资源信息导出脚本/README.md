# vCenter VM Resource Info Export Script | vCenter 虚拟机资源信息导出脚本

Automatically connects to vCenter Server, retrieves resource information for all **powered-on** virtual machines, and exports the data to an Excel file. Designed for daily data center management and resource auditing.

自动连接 vCenter Server，获取所有**开机**虚拟机的资源信息，并将其导出为 Excel 文件，便于日常数据中心管理与资源盘点。

---

## Features | 功能

- Recursively retrieves all powered-on VMs in vCenter | 递归获取 vCenter 内所有开机虚拟机
- Exports the following fields to Excel | 导出如下资源信息至 Excel：
  - VM Name | 虚拟机名称
  - CPU Cores | CPU 核心数
  - Memory (GB) | 内存（GB）
  - Total Disk Capacity (GB) | 磁盘总容量（GB）
  - Up to two IPv4 addresses | 最多两个 IPv4 地址
- Run log output | 运行日志输出
- Output filename includes the current date | 输出文件名自动包含日期

---

## Dependencies | 依赖

- Python 3.6+
- [pyvmomi](https://github.com/vmware/pyvmomi)
- [openpyxl](https://openpyxl.readthedocs.io/)

```bash
pip install pyvmomi openpyxl
```

---

## Notes | 注意事项

- Only **powered-on** VMs are exported | 仅导出"开机"状态的虚拟机
- At most two IPv4 addresses are retrieved per VM | 仅获取每台虚拟机最多两个 IPv4 地址
- SSL verification is disabled by default — modify if security is required | SSL 验证已关闭，如有安全需求请自行修改
