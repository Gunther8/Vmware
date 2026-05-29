"""
OpenClaw专用vCenter API Proxy
只允许：VM列表查询、快照列表查询、快照创建
"""

import logging
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Depends, Header, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator

from config import load_config
from auth import verify_openclaw_token
from validators import validate_vm_name, validate_operation
from rate_limiter import RateLimiter
from vcenter_client import vCenterClient
from audit_logger import AuditLogger

# 加载配置
config = load_config()

# 初始化组件
audit = AuditLogger(config.logging.audit_log_path)
rate_limiter = RateLimiter(config.security.rate_limits)
vc_client: Optional[vCenterClient] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global vc_client
    vc_client = vCenterClient(
        host=config.vcenter.host,
        port=config.vcenter.port,
        username=config.vcenter.username,
        password=config.vcenter.password,
        allowed_folder=config.vcenter.allowed_folder,
        ssl_verify=config.vcenter.ssl_verify
    )
    vc_client.connect()
    audit.log_system_event("PROXY_STARTED", "vCenter Proxy initialized")
    yield
    if vc_client:
        vc_client.disconnect()
        audit.log_system_event("PROXY_STOPPED", "vCenter Proxy shutdown")


app = FastAPI(
    title="OpenClaw vCenter Proxy",
    description="Restricted vCenter API access for OpenClaw automation",
    version="1.0.0",
    lifespan=lifespan
)


# ============ 请求/响应模型 ============

class SnapshotCreateRequest(BaseModel):
    snapshot_name: str = Field(..., min_length=1, max_length=128)
    description: Optional[str] = Field(default="", max_length=512)
    memory: bool = False
    quiesce: bool = True
    
    @validator('snapshot_name')
    def validate_name(cls, v):
        if '*' in v or '?' in v or '[' in v:
            raise ValueError('Wildcard characters not allowed')
        return v


class VMInfo(BaseModel):
    name: str
    moid: str
    power_state: str


class SnapshotInfo(BaseModel):
    name: str
    id: str
    created_at: str
    description: Optional[str]


class OperationResult(BaseModel):
    success: bool
    vm_name: str
    operation: str
    message: str
    snapshot_id: Optional[str] = None
    created_at: Optional[str] = None


# ============ 依赖注入 ============

async def require_openclaw_token(x_openclaw_token: str = Header(...)):
    """验证OpenClaw调用身份"""
    if not verify_openclaw_token(x_openclaw_token, config.openclaw.api_token):
        audit.log_security_event("AUTH_FAILED", {"token_prefix": x_openclaw_token[:8]})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing OpenClaw token"
        )
    return "openclaw"


def check_rate_limit(operation: str, vm_name: str):
    """检查操作频率限制"""
    if not rate_limiter.allow(operation, vm_name):
        audit.log_security_event("RATE_LIMIT_EXCEEDED", {
            "operation": operation,
            "vm_name": vm_name
        })
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded for {operation}"
        )


# ============ API端点 ============

@app.get("/v1/vms", response_model=List[VMInfo])
async def list_vms(
    caller: str = Depends(require_openclaw_token)
):
    """
    获取允许操作的VM列表（仅限于allowed_folder内的VM）
    OpenClaw专用接口
    """
    validate_operation("list_vms", config.security.allowed_operations)
    
    try:
        vms = vc_client.list_vms_in_folder()
        audit.log_operation(caller, "list_vms", "ALL", True, {"count": len(vms)})
        return [VMInfo(**vm) for vm in vms]
    except Exception as e:
        audit.log_operation(caller, "list_vms", "ALL", False, {"error": str(e)})
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/vms/{vm_name}/snapshots", response_model=List[SnapshotInfo])
async def list_snapshots(
    vm_name: str,
    caller: str = Depends(require_openclaw_token)
):
    """
    获取指定VM的快照列表
    OpenClaw专用接口
    """
    validate_operation("list_snapshots", config.security.allowed_operations)
    validate_vm_name(vm_name, config.security.vm_name_pattern, config.security.vm_name_max_length)
    
    try:
        snapshots = vc_client.get_snapshots(vm_name)
        audit.log_operation(caller, "list_snapshots", vm_name, True, {"count": len(snapshots)})
        return [SnapshotInfo(**snap) for snap in snapshots]
    except ValueError as e:
        audit.log_operation(caller, "list_snapshots", vm_name, False, {"error": str(e)})
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        audit.log_operation(caller, "list_snapshots", vm_name, False, {"error": str(e)})
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v1/vms/{vm_name}/snapshots", response_model=OperationResult)
async def create_snapshot(
    vm_name: str,
    request: SnapshotCreateRequest,
    caller: str = Depends(require_openclaw_token)
):
    """
    为指定VM创建快照（受严格频率限制）
    OpenClaw专用接口 - 只允许此写操作
    """
    validate_operation("create_snapshot", config.security.allowed_operations)
    validate_vm_name(vm_name, config.security.vm_name_pattern, config.security.vm_name_max_length)
    check_rate_limit("create_snapshot", vm_name)
    
    try:
        result = vc_client.create_snapshot(
            vm_name=vm_name,
            snapshot_name=request.snapshot_name,
            description=request.description,
            memory=request.memory,
            quiesce=request.quiesce
        )
        audit.log_operation(
            caller, "create_snapshot", vm_name, True,
            {"snapshot_name": request.snapshot_name, "snapshot_id": result["snapshot_id"]}
        )
        return OperationResult(
            success=True,
            vm_name=vm_name,
            operation="create_snapshot",
            message="Snapshot created successfully",
            snapshot_id=result["snapshot_id"],
            created_at=result["created_at"]
        )
    except ValueError as e:
        audit.log_operation(
            caller, "create_snapshot", vm_name, False,
            {"snapshot_name": request.snapshot_name, "error": str(e)}
        )
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        audit.log_operation(
            caller, "create_snapshot", vm_name, False,
            {"snapshot_name": request.snapshot_name, "error": str(e)}
        )
        raise HTTPException(status_code=500, detail=str(e))


# ============ 健康检查 ============

@app.get("/health")
async def health_check():
    """健康检查端点（无需认证）"""
    if vc_client and vc_client.is_connected():
        return {"status": "healthy", "vcenter_connected": True}
    return {"status": "degraded", "vcenter_connected": False}


# ============ 全局异常处理 ============

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    audit.log_security_event("UNHANDLED_EXCEPTION", {
        "path": request.url.path,
        "error": str(exc)
    })
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )
