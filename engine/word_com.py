"""Word COM 高级能力（仅 Windows）：PDF 渲染、目录刷新。

Word COM 操作在独立子进程中执行，避免 COM 单元/崩溃影响主进程。
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

_WORKER = Path(__file__).resolve().parent / "word_com_worker.py"


def is_windows() -> bool:
    return os.name == "nt"


def _run_worker(action: str, *args: str, timeout: int = 180) -> dict:
    if not is_windows():
        return {"ok": False, "message": "Word COM 仅支持 Windows"}
    cmd = [sys.executable, str(_WORKER), action, *args]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"ok": False, "message": "Word COM 操作超时"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "message": f"Word COM 子进程启动失败: {e}"}

    if proc.returncode != 0:
        return {"ok": False, "message": (proc.stderr or proc.stdout or "").strip()[:500]}
    return {"ok": True, "message": (proc.stdout or "").strip()}


def render_to_pdf(docx_path: str, pdf_path: str) -> dict:
    result = _run_worker("pdf", os.path.abspath(docx_path), os.path.abspath(pdf_path))
    if result.get("ok"):
        result["pdf_path"] = pdf_path
        result["message"] = f"已渲染 PDF: {pdf_path}"
    return result


def update_toc(docx_path: str, output_path: Optional[str] = None) -> dict:
    target = output_path or docx_path
    result = _run_worker("toc", os.path.abspath(docx_path), os.path.abspath(target))
    if result.get("ok"):
        result["message"] = f"目录已更新: {target}"
    return result


def pdf_to_png(pdf_path: str, png_dir: str, prefix: str = "page", dpi: int = 120) -> dict:
    """用 PyMuPDF 将 PDF 每页转成 PNG，返回 PNG 路径列表。"""
    try:
        import pymupdf  # noqa

        os.makedirs(png_dir, exist_ok=True)
        doc = pymupdf.open(pdf_path)
        paths = []
        for i, page in enumerate(doc):
            pix = page.get_pixmap(dpi=dpi)
            out = os.path.join(png_dir, f"{prefix}_{i + 1}.png")
            pix.save(out)
            paths.append(out)
        doc.close()
        return {"ok": True, "message": f"已生成 {len(paths)} 张 PNG", "png_paths": paths}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "message": f"PDF 转 PNG 失败: {e}"}
