"""规则校验：按段落类型抽查字号/字体/行距/缩进/对齐是否符合格式规则。"""
from __future__ import annotations

from typing import Any, Optional

from engine.classify import classify_paragraphs
from engine.document_model import DocumentModel, ParagraphModel
from rules.chinese_units import size_to_pt

SIZE_TOLERANCE = 0.5


def check_rules(model: DocumentModel, rules: dict[str, Any]) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    checked = 0

    heading_rules = {h["level"]: h for h in rules.get("headings", [])}
    body_rule = rules.get("body", {})
    special = rules.get("special", {})
    global_spacing = (rules.get("global") or {}).get("line_spacing")
    classification = classify_paragraphs(model)

    for p in model.paragraphs:
        kind, level = classification.get(p.id, ("body", None))
        if kind == "empty":
            continue

        if kind == "heading" and level in heading_rules:
            rule = heading_rules[level]
        elif kind in special:
            rule = special[kind]
        else:
            rule = body_rule

        if not rule:
            continue

        checked += 1
        _check_paragraph(p, rule, issues, global_spacing)

    return {
        "ok": len(issues) == 0,
        "checked": checked,
        "issues": issues,
        "issue_count": len(issues),
    }


def _check_paragraph(
    p: ParagraphModel,
    rule: dict,
    issues: list,
    global_spacing: Optional[float] = None,
) -> None:
    font_info = _font_info(p)
    # 字体：优先校验中文字体（east_asia），同时校验西文字体（latin_font）
    cn_expected = rule.get("font")
    latin_expected = rule.get("latin_font")
    if cn_expected:
        _check_field(p, "font", font_info.get("east_asia"), cn_expected, issues)
    if latin_expected:
        _check_field(p, "latin_font", font_info.get("font"), latin_expected, issues)

    expected_size = size_to_pt(rule.get("size"))
    _check_field(p, "size", font_info.get("size"), expected_size, issues, tolerance=SIZE_TOLERANCE)

    if rule.get("bold") is not None:
        _check_field(p, "bold", font_info.get("bold"), bool(rule["bold"]), issues)

    if rule.get("alignment"):
        _check_field(p, "alignment", p.format.alignment, rule["alignment"], issues)

    ls = rule.get("line_spacing", global_spacing)
    if ls is not None:
        _check_field(p, "line_spacing", p.format.line_spacing, ls, issues, tolerance=0.05)

    if rule.get("first_line_indent"):
        _check_field(p, "first_line_indent", p.format.first_line_indent, rule["first_line_indent"], issues)

    # 新增：标点符号检查
    _check_punctuation(p, issues)

    # 新增：西文字体检查
    _check_latin_font(p, issues)


def _check_punctuation(p: ParagraphModel, issues: list) -> None:
    """检查段落中是否有中文全角标点需要替换（保留中文句号）。"""
    FULL_PUNCT = "\uff0c\uff1b\uff1a\uff08\uff09\u201c\u201d\u2018\u2019\uff01\uff1f"
    for run in p.runs:
        if run.text and any(c in run.text for c in FULL_PUNCT):
            issues.append({
                "paragraph_id": p.id, "text": p.text[:30],
                "field": "punctuation",
                "expected": "\u82f1\u6587\u534a\u89d2\u6807\u70b9",
                "actual": "\u542b\u4e2d\u6587\u5168\u89d2\u6807\u70b9"
            })
            return


def _check_latin_font(p: ParagraphModel, issues: list) -> None:
    """检查数字/英文是否使用 Times New Roman。"""
    import re
    for run in p.runs:
        if run.text and re.search(r"[a-zA-Z0-9]", run.text):
            if run.font and run.font != "Times New Roman":
                issues.append({
                    "paragraph_id": p.id, "text": p.text[:30],
                    "field": "latin_font",
                    "expected": "Times New Roman",
                    "actual": run.font or "\u672a\u8bbe\u7f6e"
                })
                return


def _check_field(
    p: ParagraphModel,
    field: str,
    actual: Any,
    expected: Any,
    issues: list,
    tolerance: Optional[float] = None,
) -> None:
    if expected is None:
        return
    if actual is None:
        issues.append({"paragraph_id": p.id, "text": p.text[:30], "field": field, "expected": expected, "actual": None})
        return
    if tolerance is not None and isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        if abs(float(actual) - float(expected)) > tolerance:
            issues.append(
                {"paragraph_id": p.id, "text": p.text[:30], "field": field, "expected": expected, "actual": actual}
            )
        return
    if str(actual).strip() != str(expected).strip():
        issues.append(
            {"paragraph_id": p.id, "text": p.text[:30], "field": field, "expected": expected, "actual": actual}
        )


def _font_info(p: ParagraphModel) -> dict[str, Any]:
    for r in p.runs:
        if r.text.strip():
            return {"font": r.font, "east_asia": r.east_asia, "size": r.size, "bold": r.bold}
    if p.runs:
        r = p.runs[0]
        return {"font": r.font, "east_asia": r.east_asia, "size": r.size, "bold": r.bold}
    return {}
