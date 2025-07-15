# vCenter 虚拟机资源信息导出脚本

本脚本用于自动连接 vCenter Server，获取所有**开机**虚拟机的资源信息，并将其导出为 Excel 文件，便于日常数据中心管理与资源盘点。

This script connects to a vCenter Server, retrieves resource information for all **powered-on** virtual machines, and exports the data to an Excel file. It is designed for daily data center management and resource auditing.

---

## 功能 Features

- 递归获取 vCenter 内所有开机虚拟机
- 导出如下资源信息至 Excel：
  - 虚拟机名称
  - CPU 核心数
  - 内存（GB）
  - 磁盘总容量（GB）
  - 最多两个 IPv4 地址
- 运行日志输出
- 输出文件名自动包含日期

---

## 依赖 Dependencies

- Python 3.6+
- [pyvmomi](https://github.com/vmware/pyvmomi)
- [openpyxl](https://openpyxl.readthedocs.io/)
  
注意事项 Notes

仅导出“开机”状态的虚拟机

仅获取每台虚拟机最多两个 IPv4 地址

SSL 验证已关闭，如有安全需求请自行修改



