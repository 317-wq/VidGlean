"""日志与错误信息脱敏。"""

from __future__ import annotations

import re

_PATTERNS = [
    (re.compile(r"(SESSDATA\s*=\s*)[^;,\s\"']+", re.IGNORECASE), r"\1***"),
    (re.compile(r"\b(sk-[A-Za-z0-9_\-]{6})[A-Za-z0-9_\-]+"), r"\1***"),
    (re.compile(r"(Authorization:\s*Bearer\s+)\S+", re.IGNORECASE), r"\1***"),
    (re.compile(r"(\"api_key\"\s*:\s*\")[^\"]+"), r"\1***"),
    (re.compile(r"(\"sessdata\"\s*:\s*\")[^\"]+", re.IGNORECASE), r"\1***"),
]


def redact(text: str) -> str:
    if not text:
        return text
    result = text
    for pattern, replacement in _PATTERNS:
        result = pattern.sub(replacement, result)
    return result
