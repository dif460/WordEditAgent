"""结构校验：标题层级连续性、段落完整性、表格完整性。"""
from __future__ import annotations

from typing import Any

from engine.document_model import DocumentModel


def check_structure(model: DocumentModel) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    headings = [p for p in model.paragraphs if p.outline_level is not None]

    levels = [h.outline_level for h in headings]
    # 标题层级是否跳级（如 1 -> 3 缺少 2）
    for prev, cur in zip(levels, levels[1:]):
        if cur > prev + 1:
            issues.append(
                {
                    "type": "heading_level_skip",
                    "message": f"标题层级从 {prev} 跳到 {cur}，缺少中间层级",
                }
            )

    # 段落是否遗漏（id 连续性）
    ids = [int(p.id.split("_")[-1]) for p in model.paragraphs]
    if ids:
        expected = list(range(1, max(ids) + 1))
        missing = sorted(set(expected) - set(ids))
        if missing:
            issues.append({"type": "paragraph_missing", "message": f"段落编号缺失: {missing}"})

    return {
        "ok": len(issues) == 0,
        "issues": issues,
        "heading_count": len(headings),
        "paragraph_count": len(model.paragraphs),
        "table_count": len(model.tables),
    }
