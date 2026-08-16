"""AgentState：LangGraph 状态定义。"""
from __future__ import annotations

from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    task_id: str
    session_id: str
    file_path: str
    user_requirements: str

    # 运行时对象（不参与序列化持久化）
    controller: Any
    progress_callback: Any

    # 文档模型（dict）
    document_model: dict
    before_model: dict
    document_overview: dict

    # 规则与计划
    format_rules: dict
    plan: list[dict]
    current_step: int

    # 执行与校验
    tool_log: list[dict]
    verification_report: dict
    retry_count: int
    max_retry: int

    # 结果
    output_path: str
    preview: dict
    report: dict
    error: str
