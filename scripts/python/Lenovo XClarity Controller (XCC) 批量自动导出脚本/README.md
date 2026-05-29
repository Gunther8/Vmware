# Lenovo XClarity Controller (XCC) Batch Auto-Export Script | XCC 批量自动导出脚本

A Selenium-based automation script for the Lenovo XClarity Controller (BMC) web management portal. It automatically logs into multiple servers in batch, exports health/asset/alert data to Excel files, archives them by server IP, and saves unified run logs.

本项目是针对 Lenovo XClarity Controller (BMC) Web 管理后台的自动导出数据脚本。脚本基于 Selenium 实现，可自动批量登录多台服务器，导出健康/资产/告警等数据为 Excel 文件，并按服务器 IP 自动归档，运行日志统一保存。

## Compatibility | 兼容性说明

- **Supports BMC 7.x and 8.x** (e.g., 7.00, 7.20, 8.60, 8.82). As long as the web portal has an "Export Excel" button, batch export works automatically.
  **支持 BMC 7.x 和 8.x 版本**（如 7.00、7.20、8.60、8.82 等），只要 Web 页面有"导出Excel"按钮，均可自动化批量导出。
- **Does NOT support BMC 9.x+** (e.g., 9.87). The new portal removed Excel export and only supports log file (LOG) export.
  **不支持 BMC 9.x 及以上新版本**（如 9.87），新版后台已取消 Excel 导出，仅能导出日志文件（LOG）。

> ⚠️ **Security Notice | 安全提示**: Do not expose real server IPs, credentials, or firmware versions in public environments.
> 请勿在公开环境中披露生产服务器的真实 IP、账号密码或具体固件版本号。

## Features | 功能特点

- Read server list from Excel in batch | 支持从 Excel 批量读取服务器列表
- Auto login, batch export, auto-extract and archive | 自动登录、批量导出、自动解压和归档
- Downloaded files organized by server IP | 下载文件按服务器 IP 分类存储
- Unified run logs with IP and timestamp in filename | 全过程运行日志统一存放于 `log` 文件夹，日志文件含服务器IP和时间戳
- Real-time log output synced to log files | 支持实时日志输出与日志文件同步

## Usage | 使用方法

### 1. Prepare Environment | 准备环境

- Python 3.7+
- Install dependencies | 安装依赖库：
  ```bash
  pip install selenium pandas openpyxl
  ```
- Chrome browser + matching ChromeDriver installed | 已安装 Chrome 浏览器及匹配版本的 ChromeDriver

### 2. Server List File | 服务器列表文件

Create `server_list.xlsx` in the project root | 在项目根目录下新建 `server_list.xlsx`：

| IP            | USERNAME | PASSWORD |
| ------------- | -------- | -------- |
| 192.168.1.100 | user1    | 123456   |
| 192.168.1.101 | admin    | abcdef   |

### 3. Run | 运行脚本

```bash
python XCC2Excel.py
```

### 4. Check Results | 查看结果

- **Downloads**: Each server's export is stored in a folder named after its IP (e.g., `192.168.1.100/`).
  **下载内容**：每台服务器的导出文件存放在以其 IP 命名的文件夹下。
- **Logs**: All run logs are saved in the `log` folder with per-server log files (with timestamps).
  **日志文件**：所有运行日志自动保存在 `log` 文件夹下，每台服务器单独一个日志文件（含时间戳）。

## Notes | 注意事项

- Only supports **BMC 7.x and 8.x**. Version 9.x+ is not supported.
  仅适用于 **7.x 和 8.x BMC**，9.x 及更高版本不支持导出 Excel！
- If export fails, manually verify the "Export to Excel" button exists in the BMC portal.
  如导出失败，请手动登录 BMC 后台确认是否有"导出为 Excel"按钮。
- Keep the server list file secure to prevent credential leakage.
  服务器信息文件仅作脚本本地使用，请妥善保存，避免泄漏。

## License

MIT License

---

> **Disclaimer | 免责声明**: For internal automation and learning only. Do not use in unauthorized environments or in violation of production security policies.
> 本项目仅供内部自动化管理和学习交流，严禁用于未授权环境或违反生产安全规范的场景。
