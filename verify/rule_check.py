"""规则校验：抽查段落字号/字体/行距/缩进是否符合格式规则。"""
from __future__ import annotations

from typing import Any, Optional

from engine.document_model import DocumentModel, ParagraphModel
from rules.chinese_units import size_to_pt

SIZE_TOLERANCE = 0.5


def check_rules(model: DocumentModel, rules: dict[str, Any]) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    checked = 0

    heading_rules = {h["level"]: h for h in rules.get("headings", [])}
    body_rule = rules.get("body", {})

    for p in model.paragraphs:
        if not p.text.strip():
            continue
        if p.outline_level is not None and p.outline_level in heading_rules:
            checked += 1
            _check_heading(p, heading_rules[p.outline_level], issues)
        elif p.outline_level is None:
            checked += 1
            _check_body(p, body_rule, issues)

    return {
        "ok": len(issues) == 0,
        "checked": checked,
        "issues": issues,
        "issue_count": len(issues),
    }


def _check_heading(p: ParagraphModel, rule: dict, issues: list) -> None:
    font_info = _font_info(p)
    _check_field(p, "font", font_info.get("east_asia") or font_info.get("font"), rule.get("font"), issues)
    expected_size = size_to_pt(rule.get("size"))
    _check_field(p, "size", font_info.get("size"), expected_size, issues, tolerance=SIZE_TOLERANCE)
    if rule.get("bold") is not None:
        _check_field(p, "bold", font_info.get("bold"), bool(rule["bold"]), issues)
    if rule.get("alignment"):
        _check_field(p, "alignment", p.format.alignment, rule["alignment"], issues)


def _check_body(p: ParagraphModel, rule: dict, issues: list) -> None:
    if not rule:
        return
    font_info = _font_info(p)
    _check_field(p, "font", font_info.get("east_asia") or font_info.get("font"), rule.get("font"), issues)
    expected_size = size_to_pt(rule.get("size"))
    _check_field(p, "size", font_info.get("size"), expected_size, issues, tolerance=SIZE_TOLERANCE)
    _check_field(p, "line_spacing", p.format.line_spacing, rule.get("line_spacing"), issues, tolerance=0.05)
    _check_field(p, "alignment", p.format.alignment, rule.get("alignment"), issues)
    if rule.get("first_line_indent"):
        _check_field(p, "first_line_indent", p.format.first_line_indent, rule["first_line_indent"], issues)


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
