中文界面 (Chinese UI)
![image](https://github.com/user-attachments/assets/993cfbbb-f234-4d31-9dd1-6ab99cd3da29)

English Interface
![image](https://github.com/user-attachments/assets/9a3bf00e-1aeb-41f3-998e-aeb8986ef53e)


# VMware 快照管理工具 v1.3

一个基于 Python 开发的小型 VMware 快照管理工具，支持图形界面操作。通过 vSphere API 直接连接 vCenter，实现虚拟机快照的批量管理。  
主要功能包括：

- 支持连接 vCenter，并自动保存多台 vCenter 的登录信息，方便下次直接选择使用。
- 支持一键导出当前所有开机虚拟机的快照情况到 Excel 文件，并自动打开查看。
- 支持删除快照：仅保留每台虚拟机最新的 2 个快照，自动删除其他旧快照。
- 支持根据 Excel 配置文件创建快照：可指定哪些虚拟机需要创建快照，以及是否包含内存。
- 创建快照前，自动判断是否已有今天（07:30 后）生成的快照，若已有则跳过，避免重复创建。
- 支持任务执行过程中的“暂停 / 继续”，方便灵活控制。
- 实时日志显示在界面，并自动保存日志到本地日志文件（格式为 `ip_时间戳.log`）。
- 优化日志格式，带有时间戳，方便追踪操作记录。

本工具基于 Python 3 和 Tkinter GUI 开发，依赖库包括 `pyVmomi`, `pyVim`, `openpyxl` 等，支持打包为 Windows 可执行程序（exe），无需安装 Python 环境即可直接使用。

⚠️ 注意事项：  
- vCenter 账户需具备快照相关的管理权限。  
- Excel 配置文件格式需正确，缺失字段将导致快照创建失败。  
- 快照删除操作不可逆，请谨慎使用！  
- 工具会保存 vCenter 连接信息，若有安全顾虑可手动删除 `vcenter_config.json` 文件。

本工具适合 VMware vCenter 环境下的管理员，便于批量管理虚拟机快照，提升运维效率。

---

# VMware Snapshot Management Tool v1.3

A lightweight VMware snapshot management tool developed with Python, featuring a user-friendly GUI. It connects directly to **vCenter** via vSphere API for efficient bulk snapshot operations.  
Key features:

- Supports connecting to vCenter, with automatic saving of multiple vCenter login records for easy reuse.
- One-click **export of snapshot information** for all powered-on virtual machines into an Excel file, automatically opened for review.
- Supports **deleting snapshots**: keeps only the latest 2 snapshots for each VM and removes the older ones automatically.
- Supports **creating snapshots based on an Excel configuration file**, specifying which VMs require snapshots and whether to include memory.
- Before creating snapshots, the tool checks if a snapshot already exists **today after 07:30 AM** (based on the snapshot name). If it exists, snapshot creation will be skipped to avoid duplicates.
- Provides **Pause / Resume** control during task execution for greater flexibility.
- Real-time logging displayed in the GUI, with logs also saved automatically to a local log file (named as `ip_timestamp.log`).
- Optimized log format with timestamps for easy tracking and auditing.

The tool is developed with **Python 3** and **Tkinter GUI**, relying on libraries like `pyVmomi`, `pyVim`, and `openpyxl`. It supports packaging into a Windows standalone executable (`.exe`) for direct use without requiring a Python runtime.

⚠️ Notes:  
- The vCenter account must have **permissions for snapshot management**.  
- The Excel configuration file must be formatted correctly; missing fields will cause snapshot creation to fail.  
- Snapshot deletion is **irreversible**, please use this feature with caution.  
- The tool saves vCenter connection info in `vcenter_config.json`. If there are security concerns, you can delete this file manually.

This tool is designed for administrators working in VMware vCenter environments, making bulk snapshot management easier and more efficient.
