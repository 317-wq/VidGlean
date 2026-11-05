"""日志初始化：文件轮转 + 敏感信息脱敏 + 过期清理。"""

from __future__ import annotations

import logging
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

from vidglean import config
from vidglean.security.redact import redact

LOG_NAME = "vidglean.log"
_MAX_BYTES = 5 * 1024 * 1024
_BACKUP_COUNT = 3


class RedactFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:  # pragma: no cover
            return True
        record.msg = redact(message)
        record.args = ()
        return True


def log_file() -> Path:
    return config.logs_dir() / LOG_NAME


def setup_logging(level: int = logging.INFO) -> None:
    config.logs_dir().mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    if any(isinstance(h, RotatingFileHandler) for h in root.handlers):
        return
    root.setLevel(level)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")

    file_handler = RotatingFileHandler(
        log_file(), maxBytes=_MAX_BYTES, backupCount=_BACKUP_COUNT, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    file_handler.addFilter(RedactFilter())
    root.addHandler(file_handler)

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    console.addFilter(RedactFilter())
    root.addHandler(console)

    # 第三方库的请求日志过于嘈杂
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def cleanup_old_logs(retention_days: int) -> int:
    """删除超过保留期的轮转日志，返回删除的文件数。"""
    if retention_days <= 0:
        return 0
    cutoff = time.time() - retention_days * 86400
    removed = 0
    for path in config.logs_dir().glob(f"{LOG_NAME}.*"):
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink()
                removed += 1
        except OSError:
            continue
    return removed


def read_logs(since: str | None = None, until: str | None = None) -> str:
    """读取日志文本，按可选时间范围过滤（格式 YYYY-MM-DD）。"""
    path = log_file()
    if not path.exists():
        return ""
    lines = path.read_text("utf-8", errors="replace").splitlines()
    if not since and not until:
        return redact("\n".join(lines))
    selected = []
    for line in lines:
        stamp = line[:10]
        if since and stamp < since:
            continue
        if until and stamp > until:
            continue
        selected.append(line)
    return redact("\n".join(selected))
