"""
配置管理模块
"""

import os
import yaml
from dataclasses import dataclass
from typing import List, Dict, Any


@dataclass
class OpenClawConfig:
    api_token: str


@dataclass
class vCenterConfig:
    host: str
    port: int
    username: str
    password: str
    allowed_folder: str
    ssl_verify: bool


@dataclass
class SecurityConfig:
    allowed_operations: List[str]
    vm_name_pattern: str
    vm_name_max_length: int
    rate_limits: Dict[str, Dict[str, int]]


@dataclass
class LoggingConfig:
    audit_log_path: str
    log_format: str


@dataclass
class Config:
    openclaw: OpenClawConfig
    vcenter: vCenterConfig
    security: SecurityConfig
    logging: LoggingConfig


def _resolve_env_vars(value: Any) -> Any:
    """解析环境变量引用 ${VAR_NAME}"""
    if isinstance(value, str) and value.startswith('${') and value.endswith('}'):
        var_name = value[2:-1]
        return os.getenv(var_name, value)
    return value


def _deep_resolve(obj: Any) -> Any:
    """递归解析对象中的环境变量"""
    if isinstance(obj, dict):
        return {k: _deep_resolve(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_deep_resolve(item) for item in obj]
    else:
        return _resolve_env_vars(obj)


def load_config(config_path: str = "config/proxy.yaml") -> Config:
    """加载YAML配置文件"""
    with open(config_path, 'r', encoding='utf-8') as f:
        raw = yaml.safe_load(f)
    
    data = _deep_resolve(raw)
    
    return Config(
        openclaw=OpenClawConfig(
            api_token=data['openclaw']['api_token']
        ),
        vcenter=vCenterConfig(
            host=data['vcenter']['host'],
            port=data['vcenter']['port'],
            username=data['vcenter']['username'],
            password=data['vcenter']['password'],
            allowed_folder=data['vcenter']['allowed_folder'],
            ssl_verify=data['vcenter']['ssl_verify']
        ),
        security=SecurityConfig(
            allowed_operations=data['security']['allowed_operations'],
            vm_name_pattern=data['security']['vm_name_pattern'],
            vm_name_max_length=data['security']['vm_name_max_length'],
            rate_limits=data['security']['rate_limits']
        ),
        logging=LoggingConfig(
            audit_log_path=data['logging']['audit_log_path'],
            log_format=data['logging']['audit_log_path']
        )
    )
