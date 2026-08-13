"""后台任务执行器：在后台线程运行 Agent 工作流并更新数据库。"""
from __future__ import annotations

import json
from typing import Any

from agent.graph import run_agent
from app.database import SessionLocal, Task

# 任务运行期控制器注册表（用于 undo）
CONTROLLERS: dict[str, Any] = {}


def run_task(task_id: str, file_path: str, requirements: str) -> None:
    db = SessionLocal()
    try:
        task = db.get(Task, task_id)
        if task is None:
            return

        def progress(message: str, value: float) -> None:
            t = db.get(Task, task_id)
            if t:
                t.progress = round(max(t.progress or 0.0, value), 2)
                db.commit()

        result = run_agent(file_path, requirements, task_id, progress_callback=progress)

        controller = result.get("controller")
        if controller is not None:
            CONTROLLERS[task_id] = controller

        preview = result.get("preview") or {}
        pngs = preview.get("png") or []
        task = db.get(Task, task_id)
        task.status = "success"
        task.progress = 1.0
        task.output_path = result.get("output_path")
        task.preview_pdf = preview.get("pdf")
        task.preview_png = pngs[0] if pngs else None
        task.format_rules = json.dumps(result.get("format_rules"), ensure_ascii=False)
        task.report = json.dumps(result.get("report"), ensure_ascii=False, default=str)
        db.commit()
    except Exception as e:  # noqa: BLE001
        db.rollback()
        task = db.get(Task, task_id)
        if task:
            task.status = "failed"
            task.error = str(e)
            db.commit()
    finally:
        db.close()
