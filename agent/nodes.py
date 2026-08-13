"""LangGraph 各节点实现。"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from agent.llm import get_json_llm
from agent.prompts import REQUIREMENTS_TO_RULES_SYSTEM
from agent.state import AgentState
from agent.tools import call_tool
from app.config import settings
from engine.backup import backup_file
from engine.controller import DocumentController
from engine.document_model import DocumentModel
from rules.loader import detect_template, load_rule_template, merge_rules, normalize_rules
from verify.diff_report import diff_report
from verify.render import render_preview
from verify.rule_check import check_rules
from verify.structure_check import check_structure

# 标题识别正则（按优先级）
_HEADING_PATTERNS: list[tuple[int, re.Pattern]] = [
    (1, re.compile(r"^第[一二三四五六七八九十百千0-9]+章")),
    (2, re.compile(r"^第[一二三四五六七八九十百千0-9]+节")),
    (3, re.compile(r"^\d+\.\d+\.\d+")),
    (2, re.compile(r"^\d+\.\d+")),
    (2, re.compile(r"^[一二三四五六七八九十]+、")),
    (3, re.compile(r"^（[一二三四五六七八九十]+）")),
    (2, re.compile(r"^\d+[、.．]\s*")),
]


def _emit(state: AgentState, message: str, progress: float) -> None:
    cb = state.get("progress_callback")
    if cb:
        try:
            cb(message, progress)
        except Exception:
            pass


# ---- 节点 ----
def load_document(state: AgentState) -> dict[str, Any]:
    controller = DocumentController(state["file_path"])
    model = controller.model()
    _emit(state, "文档加载完成", 0.05)
    return {
        "controller": controller,
        "document_model": model.model_dump(),
        "before_model": model.model_dump(),
    }


def analyze_document(state: AgentState) -> dict[str, Any]:
    model = DocumentModel(**state["document_model"])
    overview = model.overview()
    _emit(state, f"结构分析完成：共 {overview['paragraph_count']} 段，{overview['heading_count']} 个标题", 0.10)
    return {"document_overview": overview}


def parse_requirements(state: AgentState) -> dict[str, Any]:
    requirements = state.get("user_requirements", "")
    if not requirements.strip():
        return {"format_rules": {}}
    llm = get_json_llm()
    resp = llm.invoke(
        [SystemMessage(content=REQUIREMENTS_TO_RULES_SYSTEM), HumanMessage(content=requirements)]
    )
    parsed = _safe_json(resp.content)
    _emit(state, "需求解析完成", 0.15)
    return {"format_rules": parsed}


def build_rules(state: AgentState) -> dict[str, Any]:
    parsed = state.get("format_rules") or {}
    template_name = detect_template(state.get("user_requirements", ""))
    template = load_rule_template(template_name)
    merged = merge_rules(template, parsed)
    normalized = normalize_rules(merged)
    _emit(state, f"格式规则已生成（模板：{template_name}）", 0.20)
    return {"format_rules": normalized}


def plan_format(state: AgentState) -> dict[str, Any]:
    model = DocumentModel(**state["document_model"])
    plan = _build_plan(model, state["format_rules"])
    _emit(state, f"生成 {len(plan)} 个格式化步骤", 0.25)
    return {"plan": plan, "current_step": 0}


def execute_plan(state: AgentState) -> dict[str, Any]:
    controller: DocumentController = state["controller"]
    plan = state["plan"]
    total = len(plan)
    for i, step in enumerate(plan):
        call_tool(controller, step["tool"], step["args"])
        _emit(state, f"执行步骤 {i + 1}/{total}：{step['tool']}", 0.25 + 0.45 * (i + 1) / max(total, 1))
    model = controller.model()
    return {
        "document_model": model.model_dump(),
        "tool_log": list(controller.tool_log),
        "current_step": total,
    }


def verify_step(state: AgentState) -> dict[str, Any]:
    controller: DocumentController = state["controller"]
    model = controller.model()
    rule_report = check_rules(model, state["format_rules"])
    struct_report = check_structure(model)
    report = {
        "ok": rule_report["ok"] and struct_report["ok"],
        "rule_check": rule_report,
        "structure_check": struct_report,
    }
    _emit(state, f"校验完成：规则问题 {rule_report['issue_count']} 处", 0.75)
    return {"document_model": model.model_dump(), "verification_report": report}


def fix_and_retry(state: AgentState) -> dict[str, Any]:
    report = state.get("verification_report", {})
    issues = report.get("rule_check", {}).get("issues", [])
    plan = _build_fix_plan(issues)
    retry = state.get("retry_count", 0) + 1
    _emit(state, f"第 {retry} 次修复：{len(plan)} 个修正步骤", 0.78)
    return {"plan": plan, "current_step": 0, "retry_count": retry}


def finish_and_render(state: AgentState) -> dict[str, Any]:
    controller: DocumentController = state["controller"]
    task_id = state["task_id"]
    output_path = state.get("output_path") or str(settings.output_path / f"{task_id}.docx")

    controller.save_document(output_path)
    backup_file(state["file_path"])

    before = DocumentModel(**state["before_model"])
    after = controller.model()
    diff = diff_report(before, after)

    preview = render_preview(output_path, str(settings.output_path), task_id)

    report = {
        "diff": diff,
        "verification": state.get("verification_report"),
        "tool_log": controller.tool_log,
        "changed_count": len(controller.changed_ids),
        "retry_count": state.get("retry_count", 0),
        "output_path": output_path,
        "preview": preview,
    }
    _emit(state, "交付完成", 1.0)
    return {"output_path": output_path, "preview": preview, "report": report}


def route_after_verify(state: AgentState) -> str:
    report = state.get("verification_report", {})
    if report.get("ok"):
        return "finish_and_render"
    if state.get("retry_count", 0) < state.get("max_retry", settings.max_retry):
        return "fix_and_retry"
    return "finish_and_render"


# ---- 规划与分类 ----
def _classify_paragraphs(model: DocumentModel) -> dict[str, Optional[int]]:
    result: dict[str, Optional[int]] = {}
    for p in model.paragraphs:
        if p.outline_level is not None:
            result[p.id] = p.outline_level
            continue
        text = p.text.strip()
        level = None
        if text and len(text) <= 50:
            for lvl, pat in _HEADING_PATTERNS:
                if pat.match(text):
                    level = lvl
                    break
        result[p.id] = level
    return result


def _build_plan(model: DocumentModel, rules: dict[str, Any]) -> list[dict[str, Any]]:
    plan: list[dict[str, Any]] = []

    page = rules.get("page")
    if isinstance(page, dict) and (page.get("size") or page.get("margins")):
        plan.append({"tool": "set_section_format", "args": {"page_size": page.get("size"), "margins": page.get("margins")}})

    if rules.get("header") or rules.get("footer"):
        plan.append(
            {"tool": "set_header_footer", "args": {"header": rules.get("header"), "footer": rules.get("footer")}}
        )

    heading_rules = {h["level"]: h for h in rules.get("headings", [])}
    body_rule = rules.get("body") or {}
    classification = _classify_paragraphs(model)

    for p in model.paragraphs:
        level = classification.get(p.id)
        if level is not None and level in heading_rules:
            hr = heading_rules[level]
            args: dict[str, Any] = {"paragraph_id": p.id, "level": level}
            _font_args(args, hr)
            if hr.get("bold") is not None:
                args["bold"] = hr["bold"]
            if hr.get("alignment"):
                args["alignment"] = hr["alignment"]
            plan.append({"tool": "set_heading_style", "args": args})

            sp_args = {"paragraph_id": p.id}
            for k in ("space_before", "space_after"):
                if hr.get(k) is not None:
                    sp_args[k] = hr[k]
            if len(sp_args) > 1:
                plan.append({"tool": "set_paragraph_format", "args": sp_args})
        else:
            if not p.text.strip():
                continue
            fa: dict[str, Any] = {"paragraph_id": p.id}
            _font_args(fa, body_rule)
            if any(k in fa for k in ("font", "east_asia", "size")):
                plan.append({"tool": "set_run_font", "args": fa})

            pf_args: dict[str, Any] = {"paragraph_id": p.id}
            if body_rule.get("alignment"):
                pf_args["alignment"] = body_rule["alignment"]
            if body_rule.get("line_spacing") is not None:
                pf_args["line_spacing"] = body_rule["line_spacing"]
            if body_rule.get("first_line_indent"):
                pf_args["first_line_indent"] = body_rule["first_line_indent"]
            if len(pf_args) > 1:
                plan.append({"tool": "set_paragraph_format", "args": pf_args})

    table_rule = rules.get("tables") or {}
    if table_rule:
        for t in model.tables:
            ta: dict[str, Any] = {"table_id": t.id}
            _font_args(ta, table_rule)
            if any(k in ta for k in ("font", "east_asia", "size")):
                plan.append({"tool": "set_table_font", "args": ta})

    return plan


def _build_fix_plan(issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """根据校验失败项生成确定性修复步骤。"""
    by_para: dict[str, dict[str, Any]] = {}
    for it in issues:
        pid = it["paragraph_id"]
        by_para.setdefault(pid, {"font": False, "size": False, "bold": False, "fmt": {}})
        field = it["field"]
        expected = it["expected"]
        if field == "font":
            by_para[pid]["font"] = True
            by_para[pid]["east_asia"] = expected
            by_para[pid]["font_name"] = expected
        elif field == "size":
            by_para[pid]["size"] = True
            by_para[pid]["size_val"] = expected
        elif field == "bold":
            by_para[pid]["bold"] = True
            by_para[pid]["bold_val"] = expected
        else:
            by_para[pid]["fmt"][field] = expected

    plan: list[dict[str, Any]] = []
    for pid, d in by_para.items():
        run_args: dict[str, Any] = {"paragraph_id": pid}
        if d.get("font"):
            run_args["font"] = d.get("font_name")
            run_args["east_asia"] = d.get("east_asia")
        if d.get("size"):
            run_args["size"] = d.get("size_val")
        if d.get("bold"):
            run_args["bold"] = d.get("bold_val")
        if len(run_args) > 1:
            plan.append({"tool": "set_run_font", "args": run_args})

        fmt_args = d.get("fmt", {})
        if fmt_args:
            fmt_args = {"paragraph_id": pid, **fmt_args}
            plan.append({"tool": "set_paragraph_format", "args": fmt_args})

    return plan


def _font_args(target: dict[str, Any], rule: dict[str, Any]) -> None:
    if rule.get("font"):
        target["font"] = rule["font"]
        target["east_asia"] = rule.get("east_asia", rule["font"])
    if rule.get("size") is not None:
        target["size"] = rule["size"]


def _safe_json(text: Any) -> dict[str, Any]:
    if isinstance(text, dict):
        return text
    s = str(text or "").strip()
    s = re.sub(r"^```(?:json)?\s*", "", s)
    s = re.sub(r"\s*```$", "", s)
    try:
        data = json.loads(s)
    except Exception:
        m = re.search(r"\{.*\}", s, re.DOTALL)
        try:
            data = json.loads(m.group(0)) if m else {}
        except Exception:
            data = {}
    return data if isinstance(data, dict) else {}
