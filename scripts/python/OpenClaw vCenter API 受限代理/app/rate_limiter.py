"""
操作频率限制器 - 防止滥用
"""

import time
from collections import defaultdict
from dataclasses import dataclass


@dataclass
class RateLimitConfig:
    max_requests: int
    window_seconds: int


class RateLimiter:
    """基于滑动窗口的频率限制器"""
    
    def __init__(self, config: dict):
        self.config = {
            op: RateLimitConfig(**cfg) 
            for op, cfg in config.items()
        }
        # 存储结构: {operation: {resource: [(timestamp, count)]}}
        self._windows = defaultdict(lambda: defaultdict(list))
    
    def allow(self, operation: str, resource: str = "default") -> bool:
        """
        检查是否允许操作
        resource通常是VM名称，实现按VM的独立限制
        """
        if operation not in self.config:
            return True  # 未配置限制的操作允许通过
        
        cfg = self.config[operation]
        now = time.time()
        window_key = (operation, resource)
        
        # 清理过期记录
        cutoff = now - cfg.window_seconds
        self._windows[window_key] = [
            (ts, cnt) for ts, cnt in self._windows[window_key] 
            if ts > cutoff
        ]
        
        # 计算当前窗口内请求数
        current_count = sum(cnt for ts, cnt in self._windows[window_key])
        
        if current_count >= cfg.max_requests:
            return False
        
        # 记录本次请求
        self._windows[window_key].append((now, 1))
        return True
