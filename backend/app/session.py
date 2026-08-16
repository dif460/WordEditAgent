"""Session 依赖：从请求头 X-Session-Id 提取会话标识，用于多用户隔离。"""
from __future__ import annotations

from fastapi import Header, HTTPException


def get_session_id(x_session_id: str = Header(default="", alias="X-Session-Id")) -> str:
    if not x_session_id:
        raise HTTPException(status_code=400, detail="缺少 X-Session-Id 请求头")
    return x_session_id