"""
pyvmomi封装 - 严格受限的vCenter操作
只允许读取和快照创建，禁止所有其他操作
"""

import ssl
from datetime import datetime
from typing import List, Dict, Optional

from pyVim.connect import SmartConnect, Disconnect
from pyVmomi import vim, vmodl


class vCenterClient:
    """
    OpenClaw专用vCenter客户端
    严格限制操作范围：只允许在指定Folder内查询VM和创建快照
    """
    
    def __init__(self, host: str, port: int, username: str, password: str,
                 allowed_folder: str, ssl_verify: bool = True):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.allowed_folder_name = allowed_folder
        self.ssl_verify = ssl_verify
        self.si = None
        self.allowed_folder = None
        
    def connect(self):
        """建立vCenter连接"""
        ssl_context = ssl.create_default_context()
        if not self.ssl_verify:
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
        self.si = SmartConnect(
            host=self.host,
            port=self.port,
            user=self.username,
            pwd=self.password,
            sslContext=ssl_context
        )
        
        # 定位到允许的Folder
        self.allowed_folder = self._get_folder(self.allowed_folder_name)
        if not self.allowed_folder:
            raise RuntimeError(f"Allowed folder '{self.allowed_folder_name}' not found")
    
    def disconnect(self):
        """断开vCenter连接"""
        if self.si:
            Disconnect(self.si)
            self.si = None
    
    def is_connected(self) -> bool:
        """检查连接状态"""
        return self.si is not None
    
    def _get_folder(self, folder_name: str) -> Optional[vim.Folder]:
        """获取指定名称的Folder"""
        content = self.si.RetrieveContent()
        for child in content.rootFolder.childEntity:
            if hasattr(child, 'vmFolder'):
                for folder in child.vmFolder.childEntity:
                    if isinstance(folder, vim.Folder) and folder.name == folder_name:
                        return folder
        return None
    
    def _get_vm_in_folder(self, vm_name: str) -> Optional[vim.VirtualMachine]:
        """
        在允许的Folder内查找VM
        严格边界控制：只搜索allowed_folder内的VM
        """
        if not self.allowed_folder:
            raise RuntimeError("Not connected to vCenter")
        
        for vm in self.allowed_folder.childEntity:
            if isinstance(vm, vim.VirtualMachine) and vm.name == vm_name:
                return vm
        return None
    
    def list_vms_in_folder(self) -> List[Dict]:
        """
        列出允许Folder内的所有VM
        仅返回基本信息，不包含敏感数据
        """
        vms = []
        for vm in self.allowed_folder.childEntity:
            if isinstance(vm, vim.VirtualMachine):
                vms.append({
                    "name": vm.name,
                    "moid": vm._moId,
                    "power_state": vm.runtime.powerState
                })
        return vms
    
    def get_snapshots(self, vm_name: str) -> List[Dict]:
        """
        获取VM的快照列表
        严格边界检查：只处理allowed_folder内的VM
        """
        vm = self._get_vm_in_folder(vm_name)
        if not vm:
            raise ValueError(f"VM '{vm_name}' not found in allowed folder")
        
        snapshots = []
        if vm.snapshot:
            self._traverse_snapshots(vm.snapshot.rootSnapshotList, snapshots)
        return snapshots
    
    def _traverse_snapshots(self, snapshot_list, result: List[Dict]):
        """递归遍历快照树"""
        for snap in snapshot_list:
            result.append({
                "name": snap.name,
                "id": snap.snapshot._moId,
                "created_at": snap.createTime.isoformat(),
                "description": snap.description
            })
            if snap.childSnapshotList:
                self._traverse_snapshots(snap.childSnapshotList, result)
    
    def create_snapshot(self, vm_name: str, snapshot_name: str,
                       description: str = "", memory: bool = False,
                       quiesce: bool = True) -> Dict:
        """
        创建VM快照 - 唯一允许的写操作
        严格边界检查 + 参数白名单
        """
        vm = self._get_vm_in_folder(vm_name)
        if not vm:
            raise ValueError(f"VM '{vm_name}' not found in allowed folder")
        
        # 构建任务规范（仅允许这些参数）
        task = vm.CreateSnapshot(
            name=snapshot_name,
            description=description,
            memory=memory,
            quiesce=quiesce
        )
        
        # 等待任务完成
        self._wait_for_task(task)
        
        if task.info.state != vim.TaskInfo.State.success:
            raise RuntimeError(f"Snapshot creation failed: {task.info.error}")
        
        return {
            "snapshot_id": task.info.result._moId if task.info.result else "unknown",
            "created_at": datetime.utcnow().isoformat() + "Z"
        }
    
    def _wait_for_task(self, task):
        """等待vCenter任务完成"""
        while task.info.state in [vim.TaskInfo.State.queued, vim.TaskInfo.State.running]:
            pass  # 实际生产应添加适当延迟
