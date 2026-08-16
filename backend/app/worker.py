"""后台任务执行器：在后台线程运行 Agent 工作流并更新数据库。"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from typing import Any

from docx import Document

from agent.graph import run_agent
from app.database import SessionLocal, Task
from verify.render import render_preview

# 任务运行期控制器注册表（用于 undo），key 为 "session_id:task_id"
CONTROLLERS: dict[str, Any] = {}
_ctrl_lock = threading.Lock()

# 限制同时运行的任务数，防止资源耗尽
_MAX_CONCURRENT = 3
_task_semaphore = threading.Semaphore(_MAX_CONCURRENT)


def _render_preview_background(task_id: str, output_path: str, session_id: str) -> None:
    """在后台渲染预览，完成后更新数据库。"""
    from app.config import settings

    db = SessionLocal()
    try:
        user_dir = settings.output_path / session_id
        user_dir.mkdir(parents=True, exist_ok=True)
        preview = render_preview(output_path, str(user_dir), task_id)
        task = db.get(Task, task_id)
        if task:
            pngs = preview.get("png") or []
            task.preview_pdf = preview.get("pdf")
            task.preview_png = pngs[0] if pngs else None
            db.commit()
    except Exception:
        pass
    finally:
        db.close()


def _estimate_seconds(file_path: str) -> int:
    """根据文档段落数估算处理时间（秒）。每段约 0.5 秒，最少 5 秒，最多 120 秒。"""
    try:
        doc = Document(file_path)
        para_count = len(doc.paragraphs)
        return min(max(int(para_count * 0.5), 5), 120)
    except Exception:
        return 30


def run_task(task_id: str, file_path: str, requirements: str, session_id: str) -> None:
    if not _task_semaphore.acquire(blocking=False):
        # 超过并发上限，标记为失败
        db = SessionLocal()
        try:
            task = db.get(Task, task_id)
            if task:
                task.status = "failed"
                task.completed_at = datetime.now(timezone.utc)
                task.error = "系统繁忙，请稍后重试"
                db.commit()
        finally:
            db.close()
        return

    db = SessionLocal()
    try:
        task = db.get(Task, task_id)
        if task is None:
            return

        task.estimated_seconds = _estimate_seconds(file_path)
        task.started_at = datetime.now(timezone.utc)
        task.status = "running"
        db.commit()

        _last_progress = [0.0]

        def progress(message: str, value: float) -> None:
            if value - _last_progress[0] < 0.05 and value < 1.0:
                return
            _last_progress[0] = value
            t = db.get(Task, task_id)
            if t:
                t.progress = round(max(t.progress or 0.0, value), 2)
                db.commit()

        result = run_agent(file_path, requirements, task_id, session_id, progress_callback=progress)

        controller = result.get("controller")
        if controller is not None:
            with _ctrl_lock:
                CONTROLLERS[f"{session_id}:{task_id}"] = controller

        output_path = result.get("output_path", "")
        task = db.get(Task, task_id)
        task.status = "success"
        task.progress = 1.0
        task.completed_at = datetime.now(timezone.utc)
        task.output_path = output_path
        task.format_rules = json.dumps(result.get("format_rules"), ensure_ascii=False)
        task.report = json.dumps(result.get("report"), ensure_ascii=False, default=str)
        db.commit()

        # 后台渲染预览
        if output_path:
            threading.Thread(
                target=_render_preview_background,
                args=(task_id, output_path, session_id),
                daemon=True,
            ).start()

    except Exception as e:  # noqa: BLE001
        db.rollback()
        task = db.get(Task, task_id)
        if task:
            task.status = "failed"
            task.completed_at = datetime.now(timezone.utc)
            task.error = str(e)
            db.commit()
    finally:
        db.close()
        _task_semaphore.release()