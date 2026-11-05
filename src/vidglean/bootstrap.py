"""应用初始化：目录、数据库、内置模板、日志、并发设置。"""

from __future__ import annotations

import logging

from vidglean import config, templates_builtin
from vidglean.ai import client as ai_client
from vidglean.core.utils import now_iso
from vidglean.logging_setup import cleanup_old_logs, setup_logging
from vidglean.store import db, repo

_log = logging.getLogger(__name__)


def _load_dotenv() -> None:
    """开发期读取当前目录的 .env（不覆盖已有环境变量）。"""
    try:
        from pathlib import Path

        from dotenv import load_dotenv

        candidate = Path.cwd() / ".env"
        if candidate.exists():
            load_dotenv(candidate, override=False)
    except Exception:  # pragma: no cover - 可选依赖
        pass


def seed_templates() -> None:
    for item in templates_builtin.BUILTIN_TEMPLATES:
        if repo.get_template(item["id"]) is None:
            db.execute(
                "INSERT INTO templates (id, name, kind, description, path, is_default, created_at) "
                "VALUES (?,?,?,?,?,0,?)",
                (item["id"], item["name"], "builtin", item["description"], "", now_iso()),
            )


def apply_settings() -> dict:
    settings = repo.get_settings()
    ai_client.set_concurrency(int(settings.get("concurrency_ai") or 2))
    return settings


def init() -> None:
    _load_dotenv()
    config.ensure_dirs()
    setup_logging()
    db.init_db()
    seed_templates()
    interrupted = repo.mark_running_interrupted()
    if interrupted:
        _log.warning("发现 %d 个上次未完成的任务，已标记为中断", interrupted)
    settings = apply_settings()
    removed = cleanup_old_logs(int(settings.get("log_retention_days") or 30))
    if removed:
        _log.info("清理过期日志 %d 个", removed)
