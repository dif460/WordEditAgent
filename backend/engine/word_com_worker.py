"""Word COM 子进程 worker：在独立进程中执行 COM 操作，隔离崩溃与 COM 单元问题。

用法：
    python word_com_worker.py pdf <docx> <pdf>
    python word_com_worker.py toc <docx> <out>
"""
from __future__ import annotations

import os
import sys


def _render_pdf(docx: str, pdf: str) -> None:
    import pythoncom
    import win32com.client

    pythoncom.CoInitialize()
    word = None
    try:
        word = win32com.client.DispatchEx("Word.Application")
        word.Visible = False
        word.DisplayAlerts = 0
        doc = word.Documents.Open(os.path.abspath(docx), ReadOnly=True)
        for section in doc.Sections:
            for hf in (section.Headers, section.Footers):
                for obj in hf:
                    try:
                        obj.Range.Fields.Update()
                    except Exception:
                        pass
        try:
            doc.Fields.Update()
        except Exception:
            pass
        doc.ExportAsFixedFormat(OutputFileName=os.path.abspath(pdf), ExportFormat=17)
        doc.Close(False)
    finally:
        if word is not None:
            try:
                word.Quit()
            except Exception:
                pass
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass


def _update_toc(docx: str, out: str) -> None:
    import pythoncom
    import win32com.client

    pythoncom.CoInitialize()
    word = None
    try:
        word = win32com.client.DispatchEx("Word.Application")
        word.Visible = False
        word.DisplayAlerts = 0
        doc = word.Documents.Open(os.path.abspath(docx))
        for story in doc.StoryRanges:
            try:
                story.Fields.Update()
            except Exception:
                pass
        doc.SaveAs(os.path.abspath(out))
        doc.Close(False)
    finally:
        if word is not None:
            try:
                word.Quit()
            except Exception:
                pass
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass


def main() -> None:
    action = sys.argv[1]
    if action == "pdf":
        _render_pdf(sys.argv[2], sys.argv[3])
    elif action == "toc":
        _update_toc(sys.argv[2], sys.argv[3])
    else:
        raise SystemExit(f"未知 action: {action}")
    print("OK")


if __name__ == "__main__":
    main()
