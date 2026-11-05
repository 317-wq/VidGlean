"""平台适配。第一版只支持 Bilibili。"""

from __future__ import annotations

from types import ModuleType

from vidglean.core.errors import AppError
from vidglean.platforms import bilibili

PLATFORMS = [bilibili]


def detect(url: str) -> ModuleType:
    for module in PLATFORMS:
        if module.is_supported(url):
            return module
    raise AppError("UNSUPPORTED_URL", "暂不支持该链接，目前仅支持 Bilibili")
