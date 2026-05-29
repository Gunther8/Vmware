"""
结构化审计日志 - 支持ELK/SIEM对接
"""

import json
import logging
from datetime import datetime
from pathlib import Path


class AuditLogger:
    """
    OpenClaw操作审计日志
    所有关键操作、安全事件、系统事件均记录
    """
    
    def __init__(self, log_path: str):
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 配置JSON格式日志
        self.logger = logging.getLogger("vcenter_proxy_audit")
        self.logger.setLevel(logging.INFO)
        
        handler = logging.FileHandler(log_path)
        handler.setFormatter(logging.Formatter('%(message)s'))
        self.logger.addHandler(handler)
    
    def _log(self, event_type: str, data: dict):
        """写入结构化日志"""
        entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "event_type": event_type,
            **data
        }
        self.logger.info(json.dumps(entry))
    
    def log_operation(self, caller: str, operation: str, target: str, 
                      success: bool, details: dict = None):
        """记录OpenClaw操作"""
        self._log("OPERATION", {
            "caller": caller,
            "operation": operation,
            "target": target,
            "success": success,
            "details": details or {}
        })
    
    def log_security_event(self, event: str, details: dict):
        """记录安全相关事件"""
        self._log("SECURITY", {
            "event": event,
            "details": details
        })
    
    def log_system_event(self, event: str, message: str):
        """记录系统事件"""
        self._log("SYSTEM", {
            "event": event,
            "message": message
        })
