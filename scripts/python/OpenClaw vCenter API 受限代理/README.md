# OpenClaw vCenter API Proxy | OpenClaw vCenter API 受限代理

A restricted vCenter API proxy layer designed exclusively for OpenClaw automation scenarios.

专为 OpenClaw 自动化场景设计的 vCenter API 受限代理层。

## Design Principles | 定位与原则

- **OpenClaw-only**: The Proxy is the sole entry point for OpenClaw to access vCenter.
  **OpenClaw 专用**：Proxy 是 OpenClaw 访问 vCenter 的唯一入口。
- **Zero credential exposure**: OpenClaw holds no vCenter credentials.
  **零凭证暴露**：OpenClaw 不持有任何 vCenter 账号或密码。
- **Least privilege**: Only snapshot-related operations are permitted.
  **最小权限**：仅允许快照相关操作（查询列表、查询快照、创建快照）。
- **Auditable**: All operations are recorded in structured JSON audit logs.
  **可审计**：所有操作记录结构化审计日志（JSON格式）。

## Architecture | 架构

```
┌─────────────┐      Token Auth        ┌─────────────────┐    Dedicated Account   ┌─────────────┐
│   OpenClaw  │ ─────────────────────> │  vCenter Proxy  │ ───────────────────── >│   vCenter   │
│ (Automation │                        │  (FastAPI)      │                        │             │
│   Engine)   │ <───────────────────── │  - Auth check   │ <───────────────────── │             │
└─────────────┘     JSON Response      │  - Op whitelist │                        └─────────────┘
                                       │  - Audit log    │
                                       └─────────────────┘
```

## Allowed Operations | 功能范围

**Permitted | 允许的操作：**
- List virtual machines (`list_vms`) | 查询虚拟机列表
- List VM snapshots (`list_snapshots`) | 查询虚拟机快照信息
- Create VM snapshot (`create_snapshot`) | 创建虚拟机快照

**Explicitly Forbidden | 明确禁止：**
- Delete VMs | 删除虚拟机
- Power on/off | 开关机
- Modify network, storage, or hardware config | 修改网络、存储、硬件配置
- Any wildcard or bulk operations | 任何批量或通配符操作

## Quick Start | 快速开始

### 1. Install dependencies | 安装依赖

```bash
pip install -r requirements.txt
```

### 2. Configure | 配置

```bash
cp config/proxy.yaml.example config/proxy.yaml
# Edit config/proxy.yaml with your values | 编辑填入实际值
```

### 3. Set environment variables | 设置环境变量

```bash
export VCENTER_PROXY_PASSWORD="your-vcenter-password"
export OPENCLAW_API_TOKEN="your-secret-token"
```

### 4. Start service | 启动服务

```bash
./start.sh
```

Service starts at `http://localhost:8080` | 服务将在 http://localhost:8080 启动

## API Reference | API 接口

### Authentication | 认证

All requests must include the following header | 所有请求需携带 Header：
```
X-OpenClaw-Token: your-token
```

### Endpoints | 端点

| Endpoint | Method | Description | 说明 |
|----------|--------|-------------|------|
| `/health` | GET | Health check (no auth required) | 健康检查（无需认证）|
| `/v1/vms` | GET | List allowed VMs | 获取允许操作的VM列表 |
| `/v1/vms/{vm_name}/snapshots` | GET | List snapshots for a VM | 获取指定VM的快照列表 |
| `/v1/vms/{vm_name}/snapshots` | POST | Create snapshot for a VM | 为指定VM创建快照 |

### Examples | 示例

```bash
# Health check | 健康检查
curl http://localhost:8080/health

# List VMs | 获取VM列表
curl -H "X-OpenClaw-Token: your-token" http://localhost:8080/v1/vms

# List snapshots | 获取快照列表
curl -H "X-OpenClaw-Token: your-token" \
  "http://localhost:8080/v1/vms/your-vm-name/snapshots"

# Create snapshot | 创建快照
curl -X POST -H "X-OpenClaw-Token: your-token" \
  -H "Content-Type: application/json" \
  -d '{"snapshot_name": "pre-update", "description": "Before patching"}' \
  "http://localhost:8080/v1/vms/your-vm-name/snapshots"
```

## OpenClaw Integration | OpenClaw 集成工具

The project includes `vcenter_tool.py` for direct OpenClaw invocation | 项目包含 `vcenter_tool.py`，可直接被 OpenClaw 调用：

```python
python3 vcenter_tool.py list-vms
python3 vcenter_tool.py list-snaps "vm-name"
python3 vcenter_tool.py create-snap "vm-name" "snapshot-name"
```

## Security Design | 安全设计

### Multi-layer Protection | 多层防护

1. **Token authentication** | Token 认证：OpenClaw calls require a pre-shared token.
2. **Operation whitelist** | 操作白名单：Only 3 specific endpoints allowed.
3. **VM name validation** | VM 名称校验：Wildcards and dangerous characters are blocked.
4. **Rate limiting** | 频率限制：Snapshot creation capped at 10 times per 60 seconds.
5. **Folder boundary** | Folder 边界：Only VMs within the specified Folder can be operated on.

### Audit Log | 审计日志

All operations are logged in JSON format, compatible with ELK/SIEM | 所有操作记录为 JSON 格式，支持 ELK/SIEM 对接：

```json
{
  "timestamp": "2026-02-10T10:55:04Z",
  "event_type": "OPERATION",
  "caller": "openclaw",
  "operation": "create_snapshot",
  "target": "vm-name",
  "success": true,
  "details": {"snapshot_name": "xxx", "snapshot_id": "xxx"}
}
```

## Tech Stack | 技术栈

- Python 3.10+
- FastAPI
- pyvmomi (VMware vSphere API)
- Uvicorn (ASGI Server)

## Deployment | 部署建议

### vCenter Role | vCenter 权限配置

Create a dedicated role `OpenClaw_Proxy_Role` with only | 创建专用角色，仅包含：
- `VirtualMachine.Interact.CreateSnapshot`
- `VirtualMachine.Provisioning.ReadCustSpecs`
- `System.Read`

### Network Isolation | 网络隔离

- Deploy Proxy in an isolated network segment | Proxy 部署在独立网段
- Allow only the OpenClaw host to access the Proxy API port | 仅允许 OpenClaw 主机访问 Proxy API 端口
- Proxy to vCenter via HTTPS (443) | Proxy 到 vCenter 使用 HTTPS (443)

## Disclaimer | 免责声明

For authorized automation and learning use only. Ensure you have vCenter admin authorization and comply with your organization's security policies.

本项目仅供学习和授权自动化场景使用，使用前需获得 vCenter 管理员授权并遵守所在组织的安全策略。

## License

MIT
