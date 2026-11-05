"""FastAPI 应用装配。"""

from __future__ import annotations

import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from vidglean import bootstrap
from vidglean.api.routes import (
    chat,
    documents,
    events,
    images,
    imports,
    system,
    tasks,
)
from vidglean.api.routes import (
    config as config_routes,
)
from vidglean.core.errors import AppError
from vidglean.pipeline import task_engine
from vidglean.store import db

_log = logging.getLogger(__name__)


def _web_dir() -> Path:
    """打包成 exe 后前端资源在 _MEIPASS/vidglean/web，开发态在源码目录。"""
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        return base / "vidglean" / "web"
    return Path(__file__).resolve().parent.parent / "web"


WEB_DIR = _web_dir()


@asynccontextmanager
async def lifespan(app: FastAPI):
    bootstrap.init()
    await task_engine.start()
    try:
        yield
    finally:
        await task_engine.stop()
        db.close_db()


def create_app() -> FastAPI:
    app = FastAPI(
        title="VidGlean",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.state.token = os.environ.get("VIDGLEAN_TOKEN", "")

    @app.middleware("http")
    async def token_guard(request: Request, call_next):
        token = app.state.token
        path = request.url.path
        if token and path.startswith("/api/") and not path.startswith("/api/image"):
            supplied = request.headers.get("X-VG-Token") or request.query_params.get("token")
            if supplied != token:
                return JSONResponse(
                    {
                        "ok": False,
                        "error": {
                            "code": "FORBIDDEN",
                            "message": "缺少或错误的访问令牌，请使用启动时打印的完整地址（带 token 参数）",
                        },
                    },
                    status_code=403,
                )
        return await call_next(request)

    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError):
        return JSONResponse({"ok": False, "error": exc.to_dict()}, status_code=exc.status)

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception):
        _log.exception("未处理异常 %s", request.url.path)
        return JSONResponse(
            {"ok": False, "error": {"code": "UNKNOWN", "message": "服务器内部错误"}},
            status_code=500,
        )

    for module in (system, imports, tasks, documents, chat, config_routes, events, images):
        app.include_router(module.router)

    if WEB_DIR.exists():
        app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")

    return app


app = create_app()
