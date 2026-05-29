# vCenter 8.0 Full Inspection Script | vCenter 8.0 全量巡检脚本

A vCenter 8.0 automated daily inspection tool built with Python and pyVmomi. Collects full environment data, generates an HTML report with trend charts, and pushes a summary to WeCom (Enterprise WeChat).

基于 Python + pyVmomi 开发的 vCenter 8.0 自动化巡检工具，每日自动采集全量数据，生成带趋势图的 HTML 报告，并推送摘要至企业微信。

---
<img width="1920" height="953" alt="image" src="https://github.com/user-attachments/assets/1368b81c-0a13-42bf-aed7-cc37d4309a1f" />

## Features | 功能特性

| Module | Description | 说明 |
|--------|-------------|------|
| **Resource Overview** | CPU / Memory / Storage totals, allocations, utilization, vCPU oversell ratio | CPU / 内存 / 存储总量、已分配量、实际使用率、vCPU 超售比 |
| **Cluster Details** | Per-cluster hosts, cores, memory, storage, and utilization bars | 按集群展示主机数、核心数、内存、存储及使用率进度条 |
| **VM Statistics** | Powered-on / off VM count per cluster | 各集群开机 / 关机 VM 数量汇总 |
| **VM Change Diff** | Compare with any historical date — lists added, removed, and changed VMs | 与任意历史日期比较，自动列出新增、消失、配置变更的 VM |
| **Health Alerts** | Stale snapshots / long-term power-off / VMware Tools issues / old HW version / orphaned VMs | 过期快照 / 长期关机 / VMware Tools 异常 / 旧硬件版本 / 孤立 VM |
| **Waste Analysis** | Zombie VMs (on but idle) / Oversized VMs (excess CPU/memory allocation) | 僵尸 VM（开机但长期低利用率）/ 超配 VM（CPU/内存大量闲置）|
| **Storage Analysis** | Per-datastore utilization + days-to-full prediction based on history | 各数据存储使用率 + 基于历史数据的写满天数预测 |
| **Trend Charts** | 30-day CPU / Memory / Storage / VM count line charts (Chart.js) | 近 30 天 CPU / 内存 / 存储使用率 + VM 数量折线图（Chart.js）|
| **WeCom Push** | Auto-pushes Markdown summary + HTML report attachment after each inspection | 每次巡检自动推送 Markdown 摘要 + HTML 报告附件 |

---

## Requirements | 环境要求

- Python 3.8+
- vCenter 8.0 (compatible with 7.0 | 兼容 7.0)

```bash
pip install pyVmomi requests
```

---

## Quick Start | 快速开始

**1. Configure | 修改配置**

Edit `vcenter_report.py` and fill in your environment details | 打开脚本，填写你的环境信息：

```python
VCENTER_HOST     = "your-vcenter-ip"
VCENTER_USER     = "administrator@vsphere.local"
VCENTER_PASSWORD = "your-password"

WECOM_KEY        = "your-wecom-webhook-key"
```

**2. Run | 运行**

```bash
python vcenter_report.py
```

Report is generated in the script directory | 报告生成在脚本同目录下，文件名格式：`vcenter_report_20260529_073529.html`

---

## Configurable Thresholds | 可调参数

| Parameter | Default | Description | 说明 |
|-----------|---------|-------------|------|
| `OLD_SNAPSHOT_DAYS` | 7 | Days before snapshot triggers alert | 快照超过多少天触发告警 |
| `LONG_POWEROFF_DAYS` | 30 | Consecutive power-off days for alert | 连续关机超过多少天触发告警 |
| `ZOMBIE_CPU_MHZ` | 100 | CPU usage below this = zombie candidate | 僵尸 VM 判断：CPU 用量低于此值 |
| `ZOMBIE_MEM_PCT` | 10 | Memory usage % below this = zombie candidate | 僵尸 VM 判断：内存使用率低于此值（%）|
| `OLD_HW_VER_NUM` | 14 | Hardware version below this triggers alert | 低于此硬件版本号触发告警（vmx-14）|
| `OVERSIZED_MIN_VCPU` | 8 | Min vCPU count for oversized check | 超配检测最低 vCPU 数 |
| `OVERSIZED_MIN_MEM_GB` | 16 | Min memory (GB) for oversized check | 超配检测最低内存（GB）|

---

## Data Persistence | 数据持久化

Uses SQLite (`vcenter_history.db`) for daily snapshots, enabling | 使用 SQLite 存储每日快照，支持：
- VM change history comparison | VM 变更历史对比
- Storage growth trend prediction | 存储增长趋势预测
- 30-day resource utilization trend charts | 资源使用率 30 天趋势图

The database file stays local — **do not commit to Git**.
数据库文件在本地保留，**不需要上传到 Git**。

---

## Report Layout | 报告截面示意

```
Nav: Cluster | VM Stats | Change Log | Health Alerts | Waste | Storage | Trends
├── Resource Overview Cards (CPU / Memory / Storage)
├── Cluster Resource Detail Table
├── VM Statistics Table
├── VM Change Diff (date picker + comparison tables)
├── Health Alerts (tabs: Snapshots / Power-off / Tools / HW Version / Orphaned)
├── Waste Analysis (Zombie VMs + Oversized VMs)
├── Storage Deep Analysis (utilization + fill prediction)
└── Resource Trend Charts (Chart.js, shown after ≥7 days of data)
```

---

## Dependencies | 依赖

- [pyVmomi](https://github.com/vmware/pyvmomi) — vSphere API Python bindings
- [requests](https://docs.python-requests.org/) — WeCom push notifications
- [Chart.js](https://www.chartjs.org/) — Trend charts (CDN, no install needed)

---

## License

MIT
