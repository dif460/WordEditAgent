"""前后 diff 报告：修改前后逐段对比。"""
from __future__ import annotations

from typing import Any

from engine.document_model import DocumentModel


def diff_report(before: DocumentModel, after: DocumentModel) -> dict[str, Any]:
    before_map = {p.id: p for p in before.paragraphs}
    after_map = {p.id: p for p in after.paragraphs}

    added = [pid for pid in after_map if pid not in before_map]
    deleted = [pid for pid in before_map if pid not in after_map]
    modified = []

    for pid in before_map.keys() & after_map.keys():
        bp = before_map[pid]
        ap = after_map[pid]
        changes = _para_diff(bp, ap)
        if changes:
            modified.append({"id": pid, "text": ap.text[:40], "changes": changes})

    return {
        "added": added,
        "deleted": deleted,
        "modified": modified,
        "modified_count": len(modified),
        "summary": f"新增 {len(added)} 段，删除 {len(deleted)} 段，修改 {len(modified)} 段",
    }


def _para_diff(bp, ap) -> list[str]:
    changes = []
    if bp.style != ap.style:
        changes.append(f"style: {bp.style} -> {ap.style}")
    if bp.format.alignment != ap.format.alignment:
        changes.append(f"alignment: {bp.format.alignment} -> {ap.format.alignment}")
    if bp.format.line_spacing != ap.format.line_spacing:
        changes.append(f"line_spacing: {bp.format.line_spacing} -> {ap.format.line_spacing}")
    if bp.format.first_line_indent != ap.format.first_line_indent:
        changes.append(f"first_line_indent: {bp.format.first_line_indent} -> {ap.format.first_line_indent}")

    b_run = _run_sig(bp)
    a_run = _run_sig(ap)
    if b_run != a_run:
        changes.append(f"run: {b_run} -> {a_run}")
    return changes


def _run_sig(p) -> dict:
    for r in p.runs:
        if r.text.strip():
            return {"font": r.east_asia or r.font, "size": r.size, "bold": r.bold}
    return {}
