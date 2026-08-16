"""LangGraph 工作流编排。"""
from __future__ import annotations

from typing import Any, Callable, Optional

from langgraph.graph import END, StateGraph

from agent import nodes
from agent.state import AgentState


def build_graph():
    g = StateGraph(AgentState)
    g.add_node("load_document", nodes.load_document)
    g.add_node("analyze_document", nodes.analyze_document)
    g.add_node("parse_requirements", nodes.parse_requirements)
    g.add_node("build_rules", nodes.build_rules)
    g.add_node("plan_format", nodes.plan_format)
    g.add_node("execute_plan", nodes.execute_plan)
    g.add_node("verify_step", nodes.verify_step)
    g.add_node("fix_and_retry", nodes.fix_and_retry)
    g.add_node("finish_and_render", nodes.finish_and_render)

    g.set_entry_point("load_document")
    g.add_edge("load_document", "analyze_document")
    g.add_edge("analyze_document", "parse_requirements")
    g.add_edge("parse_requirements", "build_rules")
    g.add_edge("build_rules", "plan_format")
    g.add_edge("plan_format", "execute_plan")
    g.add_edge("execute_plan", "verify_step")
    g.add_conditional_edges(
        "verify_step",
        nodes.route_after_verify,
        {"finish_and_render": "finish_and_render", "fix_and_retry": "fix_and_retry"},
    )
    g.add_edge("fix_and_retry", "execute_plan")
    g.add_edge("finish_and_render", END)

    return g.compile()


_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


def run_agent(
    file_path: str,
    requirements: str,
    task_id: str,
    session_id: str,
    progress_callback: Optional[Callable[[str, float], None]] = None,
    max_retry: Optional[int] = None,
) -> dict[str, Any]:
    """执行完整格式化流程，返回最终状态。"""
    from app.config import settings

    graph = get_graph()
    initial: AgentState = {
        "task_id": task_id,
        "session_id": session_id,
        "file_path": file_path,
        "user_requirements": requirements,
        "progress_callback": progress_callback,
        "retry_count": 0,
        "max_retry": max_retry if max_retry is not None else settings.max_retry,
        "plan": [],
        "current_step": 0,
        "tool_log": [],
    }
    result = graph.invoke(initial)
    return result
