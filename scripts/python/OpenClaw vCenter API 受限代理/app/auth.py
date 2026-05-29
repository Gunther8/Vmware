"""
Token认证模块
"""

import secrets


def verify_openclaw_token(provided_token: str, expected_token: str) -> bool:
    """
    验证OpenClaw调用Token
    使用常数时间比较防止时序攻击
    """
    if not provided_token or not expected_token:
        return False
    
    # 使用 secrets.compare_digest 防止时序攻击
    return secrets.compare_digest(provided_token, expected_token)
