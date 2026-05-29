# vCenter 8.0 全量巡检脚本

基于 Python + pyVmomi 开发的 vCenter 8.0 自动化巡检工具，每日自动采集全量数据，生成带趋势图的 HTML 报告，并推送摘要至企业微信。

---
<img width="1920" height="953" alt="image" src="https://github.com/user-attachments/assets/1368b81c-0a13-42bf-aed7-cc37d4309a1f" />

## 功能特性

| 模块 | 说明 |
|------|------|
| **资源概览** | CPU / 内存 / 存储总量、已分配量、实际使用率、vCPU 超售比 |
| **集群详情** | 按集群展示主机数、核心数、内存、存储及使用率进度条 |
| **VM 统计** | 各集群开机 / 关机 VM 数量汇总 |
| **VM 变更对比** | 与任意历史日期比较，自动列出新增、消失、配置变更的 VM |
| **健康告警** | 过期快照 / 长期关机 / VMware Tools 异常 / 旧硬件版本 / 孤立 VM |
| **资源浪费分析** | 僵尸 VM（开机但长期低利用率）/ 超配 VM（CPU/内存大量闲置）|
| **存储深度分析** | 各数据存储使用率 + 基于历史数据的写满天数预测 |
| **资源趋势图** | 近 30 天 CPU / 内存 / 存储使用率 + VM 数量折线图（Chart.js） |
| **企业微信推送** | 每次巡检自动推送 Markdown 摘要 + HTML 报告附件 |

---

## 环境要求

- Python 3.8+
- vCenter 8.0（兼容 7.0）

```bash
pip install pyVmomi requests
```

---

## 快速开始

**1. 修改配置**

打开 `vcenter_report.py`，填写你的环境信息：

```python
VCENTER_HOST     = "your-vcenter-ip"
VCENTER_USER     = "administrator@vsphere.local"
VCENTER_PASSWORD = "your-password"

WECOM_KEY        = "your-wecom-webhook-key"   # 企业微信机器人 Key
```

**2. 运行**

```bash
python vcenter_report.py
```

报告会生成在脚本同目录下，文件名格式：`vcenter_report_20260529_073529.html`


---

## 可调参数

脚本顶部的配置区域支持自定义告警阈值：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `OLD_SNAPSHOT_DAYS` | 7 | 快照超过多少天触发告警 |
| `LONG_POWEROFF_DAYS` | 30 | 连续关机超过多少天触发告警 |
| `ZOMBIE_CPU_MHZ` | 100 | 僵尸 VM 判断：CPU 用量低于此值 |
| `ZOMBIE_MEM_PCT` | 10 | 僵尸 VM 判断：内存使用率低于此值（%）|
| `OLD_HW_VER_NUM` | 14 | 低于此硬件版本号触发告警（vmx-14）|
| `OVERSIZED_MIN_VCPU` | 8 | 超配检测最低 vCPU 数 |
| `OVERSIZED_MIN_MEM_GB` | 16 | 超配检测最低内存（GB）|

---

## 数据持久化

脚本使用 SQLite（`vcenter_history.db`）存储每日快照，支持：
- VM 变更历史对比
- 存储增长趋势预测
- 资源使用率 30 天趋势图

数据库文件在本地保留，**不需要上传到 Git**。

---

## 报告截面示意

```
导航栏: 集群资源 | VM统计 | 变更记录 | 健康告警 | 资源浪费 | 存储分析 | 趋势图
├── 资源概览卡片（CPU / 内存 / 存储）
├── 集群资源详情表格
├── VM 统计表格
├── VM 变更记录（日期选择器 + 对比表格）
├── 健康告警（Tab 切换：快照 / 关机 / Tools / 硬件版本 / 孤立）
├── 资源浪费分析（僵尸 VM + 超配 VM）
├── 存储深度分析（使用率 + 写满预测）
└── 资源趋势图（Chart.js 折线图，≥7 天数据后显示）
```

---

## 依赖

- [pyVmomi](https://github.com/vmware/pyvmomi) — vSphere API Python 绑定
- [requests](https://docs.python-requests.org/) — 企业微信推送
- [Chart.js](https://www.chartjs.org/) — 趋势图（CDN，无需安装）

---

## License

MIT
