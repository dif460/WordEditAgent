"""FastAPI 入口。"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.access_control import DeviceAccessControlMiddleware
from app.api import router
from app.config import settings
from app.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Word Format Agent", version="0.1.0", lifespan=lifespan)

# 中间件顺序：后添加的在最外层。
# CORS 放最外层：负责处理 OPTIONS 预检，并给所有响应（含 403）补跨域头；
# 设备白名单放内层：严格 MAC 白名单 + 设备凭证 Cookie（ACCESS_CONTROL_MODE=mac 时生效）。
app.add_middleware(DeviceAccessControlMiddleware)
app.add_middleware(
    CORSMiddleware,
    # 允许本机前端（Next.js dev，端口不限）以及局域网/内网设备的前端跨域访问
    allow_origin_regex=(
        r"http://(localhost|127\.0\.0\.1|\[::1\]|"
        r"10\.\d{1,3}\.\d{1,3}\.\d{1,3}|"
        r"192\.168\.\d{1,3}\.\d{1,3}|"
        r"172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})(:\d+)?"
    ),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
