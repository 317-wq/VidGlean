"""零碎工具函数。"""

from __future__ import annotations

import re
from datetime import datetime


def now_iso() -> str:
    """本地时间 ISO 字符串，精确到秒。"""
    return datetime.now().replace(microsecond=0).isoformat()


def fmt_duration(seconds: int | float | None) -> str:
    total = int(seconds or 0)
    if total <= 0:
        return "00:00"
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


_INVALID_FILENAME = re.compile(r'[\\/:*?"<>|\r\n\t]')


def safe_filename(name: str, fallback: str = "document") -> str:
    cleaned = _INVALID_FILENAME.sub("_", name).strip().strip(".")
    return cleaned[:80] or fallback


def estimate_tokens(text: str) -> int:
    """粗估 token：中文约 0.7 token/字，英文约 0.3 token/字符。"""
    if not text:
        return 0
    cjk = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    other = len(text) - cjk
    return int(cjk * 0.7 + other * 0.3)
