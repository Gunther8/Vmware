"""
输入校验层 - 阻止任何危险输入
"""

import re
from fastapi import HTTPException, status


def validate_vm_name(name: str, pattern: str, max_length: int):
    """
    严格校验VM名称
    拒绝：通配符、路径遍历、特殊字符
    """
    if len(name) > max_length:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"VM name exceeds max length of {max_length}"
        )
    
    if not re.match(pattern, name):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="VM name contains invalid characters"
        )
    
    # 额外安全检查
    dangerous = ['..', '/', '\\', '*', '?', '[', ']', '$', ';', '|', '&', '`']
    for char in dangerous:
        if char in name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"VM name cannot contain '{char}'"
            )


def validate_operation(operation: str, allowed_operations: list):
    """
    操作白名单校验
    任何不在白名单的操作直接拒绝
    """
    if operation not in allowed_operations:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Operation '{operation}' not in allowed whitelist"
        )
