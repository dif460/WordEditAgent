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
from app.worker import CONTROLLERS, run_task

router = APIRouter(prefix="/api")


class CreateTaskRequest(BaseModel):
    file_id: str
    requirements: str = ""


@router.post("/upload")
async def upload(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".docx"):
        raise HTTPException(status_code=400, detail="仅支持 .docx 文件")

    file_id = uuid.uuid4().hex
    safe_name = Path(file.filename).name
    dest = settings.upload_path / f"{file_id}.docx"
    content = await file.read()
    dest.write_bytes(content)

    return {"ok": True, "file_id": file_id, "original_filename": safe_name, "size": len(content)}


@router.post("/tasks")
def create_task(req: CreateTaskRequest, background: BackgroundTasks, db: Session = Depends(get_session)):
    src = settings.upload_path / f"{req.file_id}.docx"
    if not src.exists():
        raise HTTPException(status_code=404, detail="文件不存在，请先上传")

    task = Task(
        id=uuid.uuid4().hex,
        file_id=req.file_id,
        original_filename=f"{req.file_id}.docx",
        status="pending",
        requirements=req.requirements,
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    background.add_task(run_task, task.id, str(src), req.requirements)
    return {"ok": True, "task_id": task.id, "status": task.status}


@router.get("/tasks/{task_id}")
def get_task(task_id: str, db: Session = Depends(get_session)):
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task.to_dict()


@router.get("/tasks/{task_id}/preview")
def preview(task_id: str, type: str = "png", db: Session = Depends(get_session)):
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    if type == "pdf":
        if task.preview_pdf and Path(task.preview_pdf).exists():
            return FileResponse(task.preview_pdf, media_type="application/pdf", filename=f"{task_id}.pdf")
    else:
        if task.preview_png and Path(task.preview_png).exists():
            return FileResponse(task.preview_png, media_type="image/png", filename=f"{task_id}.png")
    raise HTTPException(status_code=404, detail="预览尚未生成")


@router.get("/tasks/{task_id}/download")
def download(task_id: str, db: Session = Depends(get_session)):
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    if not task.output_path or not Path(task.output_path).exists():
        raise HTTPException(status_code=404, detail="结果尚未生成")
    return FileResponse(
        task.output_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=f"formatted_{task_id}.docx",
    )


@router.post("/tasks/{task_id}/undo")
def undo(task_id: str, db: Session = Depends(get_session)):
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")

    controller = CONTROLLERS.get(task_id)
    if controller is None:
        raise HTTPException(status_code=409, detail="任务不支持撤销（控制器已释放）")

    result = controller.undo_last()
    if not result.get("ok"):
        raise HTTPException(status_code=409, detail=result.get("message"))

    if task.output_path:
        controller.save_document(task.output_path)
    return {"ok": True, "message": result.get("message")}
