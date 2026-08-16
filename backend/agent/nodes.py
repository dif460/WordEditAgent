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
from engine.classify import classify_paragraphs
from engine.controller import DocumentController
from engine.document_model import DocumentModel
from rules.loader import detect_template, load_rule_template, merge_rules, normalize_rules
from verify.diff_report import diff_report
from verify.rule_check import check_rules
from verify.structure_check import check_structure


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
    session_id = state.get("session_id", "")

    user_output_dir = settings.output_path / session_id
    user_output_dir.mkdir(parents=True, exist_ok=True)
    output_path = state.get("output_path") or str(user_output_dir / f"{task_id}.docx")

    controller.save_document(output_path)
    controller.update_toc()  # 保存后刷新目录字段（Word COM，尽力而为）
    backup_file(state["file_path"], str(user_output_dir / "backups"))

    before = DocumentModel(**state["before_model"])
    after = controller.model()
    diff = diff_report(before, after)

    report = {
        "diff": diff,
        "verification": state.get("verification_report"),
        "tool_log": controller.tool_log,
        "changed_count": len(controller.changed_ids),
        "retry_count": state.get("retry_count", 0),
        "output_path": output_path,
    }
    _emit(state, "文档保存完成", 1.0)
    return {"output_path": output_path, "report": report}


def route_after_verify(state: AgentState) -> str:
    report = state.get("verification_report", {})
    if report.get("ok"):
        return "finish_and_render"
    if state.get("retry_count", 0) < state.get("max_retry", settings.max_retry):
        return "fix_and_retry"
    return "finish_and_render"


# ---- 规划与分类 ----
def _build_plan(model: DocumentModel, rules: dict[str, Any]) -> list[dict[str, Any]]:
    plan: list[dict[str, Any]] = []
    classification = classify_paragraphs(model)
    special = rules.get("special") or {}
    body_rule = rules.get("body") or {}
    global_spacing = (rules.get("global") or {}).get("line_spacing")

    page = rules.get("page")
    if isinstance(page, dict) and (page.get("size") or page.get("margins")):
        plan.append({"tool": "set_section_format", "args": {"page_size": page.get("size"), "margins": page.get("margins")}})

    if isinstance(page, dict) and page.get("page_number"):
        pn = page["page_number"]
        plan.append({"tool": "set_page_number", "args": {"alignment": pn.get("alignment"), "font": pn.get("font"), "size": pn.get("size")}})

    if rules.get("header") or rules.get("footer"):
        plan.append(
            {"tool": "set_header_footer", "args": {"header": rules.get("header"), "footer": rules.get("footer")}}
        )

    # ========== 前置处理：封面/声明/日期 ==========

    # 封面表格转三线表 + 左对齐
    for t in model.tables:
        # 前 3 个表格视为封面/声明表格
        t_idx = int(t.id.split("_")[-1])
        if t_idx <= 3:
            plan.append({"tool": "convert_table_to_three_line", "args": {"table_id": t.id}})
            plan.append({"tool": "set_table_cell_alignment", "args": {"table_id": t.id, "alignment": "left"}})

    # 封面图片居中 + 标准化 + 后空行
    for p in model.paragraphs:
        kind = classification.get(p.id, ("body",))[0]
        if p.has_image and kind in ("cover", "image", "empty"):
            plan.append({"tool": "set_paragraph_format", "args": {"paragraph_id": p.id, "alignment": "center"}})
            plan.append({"tool": "normalize_image", "args": {"paragraph_id": p.id}})
            plan.append({"tool": "add_blank_after", "args": {"paragraph_id": p.id}})

    # 声明分页 + 标题格式化
    declaration_seen = False
    for p in model.paragraphs:
        kind = classification.get(p.id, ("body",))[0]
        if kind == "declaration" and not declaration_seen:
            declaration_seen = True
            plan.append({"tool": "insert_page_break_before", "args": {"paragraph_id": p.id}})
            plan.append({"tool": "set_heading_style", "args": {"paragraph_id": p.id, "level": 1, "font": "\u9ed1\u4f53", "east_asia": "\u9ed1\u4f53", "size": 14, "bold": True, "alignment": "center"}})

    # 日期清洗
    for p in model.paragraphs:
        kind = classification.get(p.id, ("body",))[0]
        if kind == "date_text":
            plan.append({"tool": "normalize_date", "args": {"paragraph_id": p.id}})

    # ========== 正文处理 ==========

    heading_rules = {h["level"]: h for h in rules.get("headings", [])}

    for p in model.paragraphs:
        kind, level = classification.get(p.id, ("body", None))

        if kind == "empty":
            if global_spacing is not None:
                plan.append({"tool": "set_paragraph_format", "args": {"paragraph_id": p.id, "line_spacing": global_spacing}})
            continue

        if kind == "heading":
            if level is not None and level in heading_rules:
                hr = heading_rules[level]
            else:
                available = sorted(heading_rules.keys())
                if available:
                    closest = min(available, key=lambda x: abs(x - (level or max(available))))
                    hr = heading_rules[closest]
                else:
                    hr = body_rule
            args: dict[str, Any] = {"paragraph_id": p.id, "level": level or 1}
            _font_args(args, hr)
            if hr.get("bold") is not None:
                args["bold"] = hr["bold"]
            if hr.get("alignment"):
                args["alignment"] = hr["alignment"]
            plan.append({"tool": "set_heading_style", "args": args})
            _add_para_format(plan, p.id, hr, global_spacing, clear_indent=True)
            continue

        # 封面/声明/日期/英文标题等特殊类型
        if kind in ("cover", "declaration", "date_text"):
            continue  # 已在前面处理

        # body 与 special 类型统一走字体+段落格式
        rule = special.get(kind) or body_rule
        if not isinstance(rule, dict):
            rule = body_rule

        fa: dict[str, Any] = {"paragraph_id": p.id}
        _font_args(fa, rule)
        if rule.get("bold") is not None:
            fa["bold"] = rule["bold"]
        if any(k in fa for k in ("font", "east_asia", "size", "bold")):
            plan.append({"tool": "set_run_font", "args": fa})

        # 正文强制首行缩进 2 字符
        _clear = kind in ("image", "formula", "figure_caption", "table_caption", "sub_heading")
        _add_para_format(plan, p.id, rule, global_spacing, clear_indent=_clear)

        # 小标题（1）（2）强制换行顶格
        if kind == "sub_heading":
            plan.append({"tool": "set_paragraph_format", "args": {"paragraph_id": p.id, "first_line_indent": "2\u5b57\u7b26"}})

    # 表格字体处理
    table_rule = rules.get("tables") or {}
    if table_rule:
        for t in model.tables:
            ta: dict[str, Any] = {"table_id": t.id}
            _font_args(ta, table_rule)
            if any(k in ta for k in ("font", "east_asia", "size")):
                plan.append({"tool": "set_table_font", "args": ta})
            if table_rule.get("alignment"):
                plan.append({"tool": "set_table_alignment", "args": {"table_id": t.id, "alignment": table_rule["alignment"]}})

    # ========== 后置处理：全局清洗 ==========

    # 图表编号重排
    plan.append({"tool": "renumber_figures_tables", "args": {}})

    # 全文标点半角清洗
    for p in model.paragraphs:
        kind = classification.get(p.id, ("body",))[0]
        if kind not in ("empty", "formula"):
            plan.append({"tool": "normalize_punctuation", "args": {"paragraph_id": p.id}})

    # 全文西文字体替换
    for p in model.paragraphs:
        if p.text.strip():
            plan.append({"tool": "batch_replace_latin_font", "args": {"paragraph_id": p.id}})

    # 图表前后空行
    for p in model.paragraphs:
        kind = classification.get(p.id, ("body",))[0]
        if kind in ("image", "figure_caption", "table_caption"):
            plan.append({"tool": "ensure_blank_around", "args": {"paragraph_id": p.id}})

    # 公式上下空行 + 末尾标点移除 + 引用上浮修正
    for p in model.paragraphs:
        kind = classification.get(p.id, ("body",))[0]
        if kind == "formula":
            plan.append({"tool": "ensure_blank_around", "args": {"paragraph_id": p.id}})
            plan.append({"tool": "strip_trailing_punctuation", "args": {"paragraph_id": p.id}})
            plan.append({"tool": "fix_formula_citation", "args": {"paragraph_id": p.id}})

    # 参考文献悬挂缩进
    for p in model.paragraphs:
        kind = classification.get(p.id, ("body",))[0]
        if kind == "references_entry":
            plan.append({"tool": "set_paragraph_format", "args": {"paragraph_id": p.id, "hanging_indent": "4\u5b57\u7b26"}})

    # 关键词分隔符统一
    for p in model.paragraphs:
        kind = classification.get(p.id, ("body",))[0]
        if kind in ("keywords", "english_keywords"):
            plan.append({"tool": "normalize_keywords", "args": {"paragraph_id": p.id}})

    # 附录分页
    for p in model.paragraphs:
        kind = classification.get(p.id, ("body",))[0]
        if kind == "appendix_heading":
            plan.append({"tool": "insert_page_break_before", "args": {"paragraph_id": p.id}})

    return plan


def _add_para_format(plan: list[dict[str, Any]], pid: str, rule: dict[str, Any], global_spacing: Optional[float], clear_indent: bool = False) -> None:
    pf_args: dict[str, Any] = {"paragraph_id": pid}
    if rule.get("alignment"):
        pf_args["alignment"] = rule["alignment"]
    ls = rule.get("line_spacing", global_spacing)
    if ls is not None:
        pf_args["line_spacing"] = ls
    if clear_indent:
        pf_args["first_line_indent"] = "0"
    elif rule.get("first_line_indent"):
        pf_args["first_line_indent"] = rule["first_line_indent"]
    if rule.get("hanging_indent"):
        pf_args["hanging_indent"] = rule["hanging_indent"]
    if rule.get("space_before") is not None:
        pf_args["space_before"] = rule["space_before"]
    if rule.get("space_after") is not None:
        pf_args["space_after"] = rule["space_after"]
    if len(pf_args) > 1:
        plan.append({"tool": "set_paragraph_format", "args": pf_args})


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
    """从规则生成字体参数。

    支持中英文分离：latin_font（西文/数字）+ font（中文）。
    生成的 font=西文字体、east_asia=中文字体，与 set_run_font 入参对应。
    """
    latin = rule.get("latin_font")
    cn = rule.get("font")
    if latin and cn:
        target["font"] = latin
        target["east_asia"] = rule.get("east_asia", cn)
    elif cn:
        target["font"] = cn
        target["east_asia"] = rule.get("east_asia", cn)
    elif latin:
        target["font"] = latin
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
