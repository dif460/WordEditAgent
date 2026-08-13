"""FastAPI 入口。"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import router
from app.config import settings
from app.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Word Format Agent", version="0.1.0", lifespan=lifespan)
app.include_router(router)


@app.get("/")
def root():
    return {
        "service": "Word Format Agent",
        "endpoints": [
            "POST /api/upload",
            "POST /api/tasks",
            "GET /api/tasks/{id}",
            "GET /api/tasks/{id}/preview",
            "GET /api/tasks/{id}/download",
            "POST /api/tasks/{id}/undo",
        ],
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
