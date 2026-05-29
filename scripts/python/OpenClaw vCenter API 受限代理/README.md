# OpenClaw vCenter API Proxy

专为 OpenClaw 自动化场景设计的 vCenter API 受限代理层。

## 定位与原则

- **OpenClaw 专用**：Proxy 是 OpenClaw 访问 vCenter 的唯一入口
- **零凭证暴露**：OpenClaw 不持有任何 vCenter 账号或密码
- **最小权限**：仅允许快照相关操作（查询列表、查询快照、创建快照）
- **可审计**：所有操作记录结构化审计日志（JSON格式）

## 架构

```
┌─────────────┐      Token认证       ┌─────────────────┐      专用账号       ┌─────────────┐
│   OpenClaw  │ ───────────────────> │  vCenter Proxy  │ ─────────────────> │   vCenter   │
│  (Automation│                      │  (FastAPI)      │                    │             │
│   Engine)   │ <─────────────────── │  - 权限校验     │ <───────────────── │             │
└─────────────┘    JSON响应          │  - 操作白名单   │                    └─────────────┘
                                    │  - 审计日志     │
                                    └─────────────────┘
```

## 功能范围

**允许的操作：**
- 查询虚拟机列表 (`list_vms`)
- 查询虚拟机快照信息 (`list_snapshots`)
- 创建虚拟机快照 (`create_snapshot`)

**明确禁止：**
- 删除虚拟机
- 开关机
- 修改网络、存储、硬件配置
- 任何批量或通配符操作

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置

```bash
cp config/proxy.yaml.example config/proxy.yaml
# 编辑 config/proxy.yaml 填入实际值
```

### 3. 设置环境变量

```bash
export VCENTER_PROXY_PASSWORD="your-vcenter-password"
export OPENCLAW_API_TOKEN="your-secret-token"
```

### 4. 启动服务

```bash
./start.sh
```

服务将在 http://localhost:8080 启动

## API 接口

### 认证

所有请求需携带 Header：
```
X-OpenClaw-Token: your-token
```

### 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/health` | GET | 健康检查（无需认证） |
| `/v1/vms` | GET | 获取允许操作的VM列表 |
| `/v1/vms/{vm_name}/snapshots` | GET | 获取指定VM的快照列表 |
| `/v1/vms/{vm_name}/snapshots` | POST | 为指定VM创建快照 |

### 示例

```bash
# 健康检查
curl http://localhost:8080/health

# 获取VM列表
curl -H "X-OpenClaw-Token: your-token" http://localhost:8080/v1/vms

# 获取快照列表
curl -H "X-OpenClaw-Token: your-token" \
  "http://localhost:8080/v1/vms/your-vm-name/snapshots"

# 创建快照
curl -X POST -H "X-OpenClaw-Token: your-token" \
  -H "Content-Type: application/json" \
  -d '{"snapshot_name": "pre-update", "description": "Before patching"}' \
  "http://localhost:8080/v1/vms/your-vm-name/snapshots"
```

## OpenClaw 集成工具

项目包含 `vcenter_tool.py`，可直接被 OpenClaw 调用：

```python
# 列出所有VM
python3 vcenter_tool.py list-vms

# 查询快照
python3 vcenter_tool.py list-snaps "vm-name"

# 创建快照
python3 vcenter_tool.py create-snap "vm-name" "snapshot-name"
```

## 安全设计

### 多层防护

1. **Token 认证**：OpenClaw 调用需携带预共享 Token
2. **操作白名单**：仅允许 3 个特定接口
3. **VM 名称校验**：禁止通配符和危险字符
4. **频率限制**：快照创建限制为 60 秒内最多 10 次
5. **Folder 边界**：仅允许操作指定 Folder 内的 VM

### 审计日志

所有操作记录为 JSON 格式，支持 ELK/SIEM 对接：

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

## 技术栈

- Python 3.10+
- FastAPI
- pyvmomi (VMware vSphere API)
- Uvicorn (ASGI Server)

## 部署建议

### vCenter 权限配置

创建专用角色 `OpenClaw_Proxy_Role`，仅包含：
- `VirtualMachine.Interact.CreateSnapshot`
- `VirtualMachine.Provisioning.ReadCustSpecs`
- `System.Read`

绑定到专用账号，并限制在指定 Folder。

### 网络隔离

- Proxy 部署在独立网段
- 仅允许 OpenClaw 主机访问 Proxy API 端口
- Proxy 到 vCenter 使用 HTTPS (443)

## 免责声明

本项目仅供学习和授权自动化场景使用。使用本工具需确保：
- 已获得 vCenter 管理员授权
- 遵守所在组织的安全策略
- 承担使用风险

## License

MIT
