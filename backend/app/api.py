"""API 路由。"""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal, Task, get_session
from app.session import get_session_id
from app.worker import CONTROLLERS, run_task

router = APIRouter(prefix="/api")


class CreateTaskRequest(BaseModel):
    file_id: str
    requirements: str = ""
    original_filename: str = ""


def _session_upload_dir(session_id: str) -> Path:
    p = settings.upload_path / session_id
    p.mkdir(parents=True, exist_ok=True)
    return p


def _session_output_dir(session_id: str) -> Path:
    p = settings.output_path / session_id
    p.mkdir(parents=True, exist_ok=True)
    return p


@router.post("/upload")
async def upload(
    file: UploadFile = File(...),
    session_id: str = Depends(get_session_id),
):
    if not file.filename or not file.filename.lower().endswith(".docx"):
        raise HTTPException(status_code=400, detail="仅支持 .docx 文件")

    file_id = uuid.uuid4().hex
    safe_name = Path(file.filename).name
    dest = _session_upload_dir(session_id) / f"{file_id}.docx"
    content = await file.read()
    dest.write_bytes(content)

    return {"ok": True, "file_id": file_id, "original_filename": safe_name, "size": len(content)}


@router.post("/tasks")
def create_task(
    req: CreateTaskRequest,
    background: BackgroundTasks,
    session_id: str = Depends(get_session_id),
    db: Session = Depends(get_session),
):
    src = _session_upload_dir(session_id) / f"{req.file_id}.docx"
    if not src.exists():
        raise HTTPException(status_code=404, detail="文件不存在，请先上传")

    task = Task(
        id=uuid.uuid4().hex,
        session_id=session_id,
        file_id=req.file_id,
        original_filename=req.original_filename or f"{req.file_id}.docx",
        status="pending",
        requirements=req.requirements,
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    background.add_task(run_task, task.id, str(src), req.requirements, session_id)
    return {"ok": True, "task_id": task.id, "status": task.status}


def _get_task_for_session(task_id: str, session_id: str, db: Session) -> Task:
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.session_id != session_id:
        raise HTTPException(status_code=403, detail="无权访问该任务")
    return task


@router.get("/tasks/{task_id}")
def get_task(
    task_id: str,
    session_id: str = Depends(get_session_id),
    db: Session = Depends(get_session),
):
    return _get_task_for_session(task_id, session_id, db).to_dict()


@router.get("/tasks/{task_id}/preview")
def preview(
    task_id: str,
    type: str = "png",
    session_id: str = Depends(get_session_id),
    db: Session = Depends(get_session),
):
    task = _get_task_for_session(task_id, session_id, db)
    if type == "pdf":
        if task.preview_pdf and Path(task.preview_pdf).exists():
            return FileResponse(task.preview_pdf, media_type="application/pdf", filename=f"{task_id}.pdf")
    else:
        if task.preview_png and Path(task.preview_png).exists():
            return FileResponse(task.preview_png, media_type="image/png", filename=f"{task_id}.png")
    raise HTTPException(status_code=404, detail="预览尚未生成")


@router.get("/tasks/{task_id}/download")
def download(
    task_id: str,
    session_id: str = Depends(get_session_id),
    db: Session = Depends(get_session),
):
    task = _get_task_for_session(task_id, session_id, db)
    if not task.output_path or not Path(task.output_path).exists():
        raise HTTPException(status_code=404, detail="结果尚未生成")
    # 用原始文件名生成下载名：报告.docx → 报告_修改版.docx
    original = Path(task.original_filename)
    download_name = f"{original.stem}_修改版{original.suffix}"
    return FileResponse(
        task.output_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=download_name,
    )


@router.post("/tasks/{task_id}/undo")
def undo(
    task_id: str,
    session_id: str = Depends(get_session_id),
    db: Session = Depends(get_session),
):
    task = _get_task_for_session(task_id, session_id, db)

    controller = CONTROLLERS.get(f"{session_id}:{task_id}")
    if controller is None:
        raise HTTPException(status_code=409, detail="任务不支持撤销（控制器已释放）")

    result = controller.undo_last()
    if not result.get("ok"):
        raise HTTPException(status_code=409, detail=result.get("message"))

    if task.output_path:
        controller.save_document(task.output_path)
    return {"ok": True, "message": result.get("message")}