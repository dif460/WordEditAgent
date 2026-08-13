"""渲染与视觉校验：Word COM 导出 PDF，再转 PNG。"""
from __future__ import annotations

import os
from typing import Any

from engine import word_com


def render_preview(docx_path: str, output_dir: str, task_id: str) -> dict[str, Any]:
    """渲染 PDF 与 PNG 预览，返回路径。"""
    os.makedirs(output_dir, exist_ok=True)
    pdf_path = os.path.join(output_dir, f"{task_id}.pdf")
    png_dir = os.path.join(output_dir, f"{task_id}_png")

    pdf_result = word_com.render_to_pdf(docx_path, pdf_path)
    if not pdf_result["ok"]:
        return {"ok": False, "pdf": None, "png": [], "message": pdf_result["message"]}

    png_result = word_com.pdf_to_png(pdf_path, png_dir, prefix=task_id)
    return {
        "ok": True,
        "pdf": pdf_path,
        "png": png_result.get("png_paths", []),
        "message": f"预览已生成：{pdf_path}",
    }
