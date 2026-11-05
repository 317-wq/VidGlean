"""系统能力：健康检查、备份恢复、日志、用量、清理、数据目录。"""

from __future__ import annotations

import base64
import hashlib
import os
import shutil
import sqlite3
import tempfile
import uuid
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from vidglean import __version__, bootstrap, config
from vidglean.api.common import ok
from vidglean.api.schemas import BackupIn, DataDirIn, RestoreIn
from vidglean.core.errors import AppError
from vidglean.logging_setup import read_logs
from vidglean.pipeline import task_engine
from vidglean.security import secrets as secret_store
from vidglean.store import db, repo

router = APIRouter(prefix="/api")

_ENCRYPT_MAGIC = b"VGENC1"


# ---------------------------------------------------------------- 健康检查


@router.get("/health")
async def health() -> dict[str, Any]:
    return ok(
        {
            "version": __version__,
            "data_dir": str(config.data_root()),
            "secrets_backend": secret_store.backend(),
            "has_model": repo.current_model() is not None,
            "has_bilibili": secret_store.has_secret("bilibili:sessdata"),
            "active_tasks": task_engine.active_count,
            "interrupted": len(repo.list_tasks(status="interrupted", limit=100)),
        }
    )


# ---------------------------------------------------------------- 用量


@router.get("/stats/usage")
async def usage(days: int = 30) -> dict[str, Any]:
    return ok(repo.usage_summary(days=days))


# ---------------------------------------------------------------- 日志


@router.get("/logs")
async def download_logs(since: str | None = None, until: str | None = None) -> PlainTextResponse:
    text = read_logs(since, until)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return PlainTextResponse(
        text,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="vidglean-{stamp}.log"'},
    )


# ---------------------------------------------------------------- 备份


def _snapshot_db(target: Path) -> None:
    source = sqlite3.connect(config.db_path())
    destination = sqlite3.connect(target)
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()


def _build_zip(target: Path) -> None:
    config.tmp_dir().mkdir(parents=True, exist_ok=True)
    snapshot = config.tmp_dir() / f"snapshot-{uuid.uuid4().hex}.db"
    _snapshot_db(snapshot)
    try:
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.write(snapshot, "vidglean.db")
            for folder in ("documents", "subtitles", "templates"):
                base = config.data_root() / folder
                if not base.exists():
                    continue
                for path in base.rglob("*"):
                    if path.is_file():
                        archive.write(path, str(path.relative_to(config.data_root())))
    finally:
        if snapshot.exists():
            snapshot.unlink()


def _encrypt(data: bytes, password: str) -> bytes:
    from cryptography.fernet import Fernet

    salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)
    token = Fernet(base64.urlsafe_b64encode(key)).encrypt(data)
    return _ENCRYPT_MAGIC + salt + token


def _decrypt(data: bytes, password: str) -> bytes:
    from cryptography.fernet import Fernet, InvalidToken

    offset = len(_ENCRYPT_MAGIC)
    if len(data) < offset + 16:
        raise AppError("CONFLICT", "备份文件损坏")
    salt = data[offset : offset + 16]
    token = data[offset + 16 :]
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)
    try:
        return Fernet(base64.urlsafe_b64encode(key)).decrypt(token)
    except InvalidToken as exc:
        raise AppError("CONFLICT", "密码错误或备份文件已损坏") from exc


@router.post("/backup")
async def backup(payload: BackupIn) -> dict[str, Any]:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    if payload.path.strip():
        target = Path(payload.path).expanduser().resolve()
        if target.is_dir():
            target = target / f"vidglean-backup-{stamp}.zip"
    else:
        target = config.data_root() / f"vidglean-backup-{stamp}.zip"
    target.parent.mkdir(parents=True, exist_ok=True)
    if payload.password:
        target = target.with_suffix(".enc")
    with tempfile.TemporaryDirectory() as tmp:
        temp_zip = Path(tmp) / "backup.zip"
        _build_zip(temp_zip)
        if payload.password:
            target.write_bytes(_encrypt(temp_zip.read_bytes(), payload.password))
        else:
            shutil.move(str(temp_zip), str(target))
    return ok({"path": str(target), "size": target.stat().st_size, "encrypted": bool(payload.password)})


@router.post("/restore")
async def restore(payload: RestoreIn) -> dict[str, Any]:
    source = Path(payload.path).expanduser().resolve()
    if not source.exists():
        raise AppError("NOT_FOUND", "备份文件不存在", status=404)
    data = source.read_bytes()
    if data.startswith(_ENCRYPT_MAGIC):
        if not payload.password:
            raise AppError("CONFLICT", "该备份已加密，需要输入密码")
        data = _decrypt(data, payload.password)
    elif payload.password:
        raise AppError("CONFLICT", "该备份未加密，请不要填写密码")
    if not data.startswith(b"PK"):
        raise AppError("CONFLICT", "备份文件格式不正确")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        archive_path = tmp_path / "restore.zip"
        archive_path.write_bytes(data)
        extract_dir = tmp_path / "extract"
        with zipfile.ZipFile(archive_path) as archive:
            archive.extractall(extract_dir)
        if not (extract_dir / "vidglean.db").exists():
            raise AppError("CONFLICT", "备份中缺少数据库文件")

        # 恢复前先备份当前数据
        safety = config.data_root() / f"pre-restore-{datetime.now().strftime('%Y%m%d-%H%M%S')}.zip"
        safety_path = str(safety)
        try:
            _build_zip(safety)
        except Exception:  # pragma: no cover - 备份失败不应阻塞恢复
            safety_path = ""

        db.close_db()
        for item in extract_dir.iterdir():
            destination = config.data_root() / item.name
            if item.name == "vidglean.db":
                for suffix in ("", "-wal", "-shm"):
                    leftover = config.data_root() / f"vidglean.db{suffix}"
                    if leftover.exists():
                        leftover.unlink()
                shutil.copy2(item, destination)
            elif item.is_dir():
                shutil.copytree(item, destination, dirs_exist_ok=True)
        db.init_db()
        bootstrap.apply_settings()
    return ok({"restored": True, "safety_backup": safety_path})


# ---------------------------------------------------------------- 清理


@router.post("/system/cleanup")
async def cleanup() -> dict[str, Any]:
    freed = 0
    removed = 0
    tmp = config.tmp_dir()
    if tmp.exists():
        for path in tmp.rglob("*"):
            if path.is_file():
                freed += path.stat().st_size
                removed += 1
                path.unlink()
    active = {row["id"] for row in repo.list_tasks(limit=1000)}
    if config.tasks_dir().exists():
        for directory in config.tasks_dir().iterdir():
            if directory.is_dir() and directory.name not in active:
                for path in directory.rglob("*"):
                    if path.is_file():
                        freed += path.stat().st_size
                shutil.rmtree(directory, ignore_errors=True)
                removed += 1
    return ok({"freed": freed, "removed": removed})


# ---------------------------------------------------------------- 数据目录


@router.post("/system/data-dir")
async def change_data_dir(payload: DataDirIn) -> dict[str, Any]:
    target = Path(payload.path).expanduser()
    if not str(target).strip():
        raise AppError("CONFLICT", "目录不能为空")
    try:
        target.mkdir(parents=True, exist_ok=True)
        probe = target / ".write-test"
        probe.write_text("ok", "utf-8")
        probe.unlink()
    except OSError as exc:
        raise AppError("CONFLICT", "目录不可写", detail=str(exc)) from exc
    db.close_db()
    new_root = config.migrate_data_root(target)
    db.init_db()
    bootstrap.apply_settings()
    return ok({"data_dir": str(new_root), "restart_required": True})


# ---------------------------------------------------------------- 更新检查


@router.post("/update/check")
async def check_update() -> dict[str, Any]:
    settings = repo.get_settings()
    url = str(settings.get("update_url") or "").strip()
    if not url:
        return ok({"available": False, "message": "未配置更新源，当前版本 " + __version__})
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(url)
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPError as exc:
        raise AppError("NETWORK", "检查更新失败", detail=str(exc)) from exc
    except ValueError as exc:
        raise AppError("CONFLICT", "更新源返回内容不是合法 JSON", detail=str(exc)) from exc
    latest = str(payload.get("version") or "")
    return ok(
        {
            "available": bool(latest and latest != __version__),
            "current": __version__,
            "latest": latest,
            "notes": payload.get("notes", ""),
            "url": payload.get("url", ""),
        }
    )


# ---------------------------------------------------------------- 调试


@router.get("/debug/state")
async def debug_state() -> dict[str, Any]:
    if os.environ.get("VIDGLEAN_DEBUG") != "1":
        raise AppError("NOT_FOUND", "未开启调试", status=404)
    return ok({"settings": repo.get_settings(), "tasks": repo.list_tasks(limit=20)})


@router.get("/debug/markdown")
async def debug_markdown(text: str) -> dict[str, Any]:
    from vidglean.markdown_render import render

    return ok({"html": render(text)})
