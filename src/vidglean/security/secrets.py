"""敏感凭证存储。

优先使用系统凭据管理器（Windows Credential Manager）。在没有可用后端的环境
（例如无桌面会话的 Linux 开发机）退化为数据目录下的 ``secrets.json``，权限 0600，
并在日志中给出明确警告。设置环境变量 ``VIDGLEAN_SECRETS=file`` 可强制使用文件后端。
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
from pathlib import Path

from vidglean import config

SERVICE = "vidglean"
_log = logging.getLogger(__name__)
_warned = False
_runtime_fallback = False

ENV_FALLBACK = {
    "bilibili:sessdata": "BILI_SESSDATA",
}

_FILE_MODE = 0o600


def _fallback_path() -> Path:
    return config.data_root() / "secrets.json"


def _keyring_usable() -> bool:
    if os.environ.get("VIDGLEAN_SECRETS", "").lower() == "file":
        return False
    try:
        import keyring
        from keyring.backends import fail

        return not isinstance(keyring.get_keyring(), fail.Keyring)
    except Exception:  # pragma: no cover - 取决于运行环境
        return False


def backend() -> str:
    if _runtime_fallback:
        return "file"
    return "system" if _keyring_usable() else "file"


def _read_file() -> dict[str, str]:
    path = _fallback_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return {}


def _write_file(data: dict[str, str]) -> None:
    path = _fallback_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")
    with contextlib.suppress(OSError):  # 非 POSIX 平台没有 chmod
        path.chmod(_FILE_MODE)


def _warn_fallback() -> None:
    global _warned, _runtime_fallback
    _runtime_fallback = True
    if _warned:
        return
    _warned = True
    _log.warning("系统凭据管理器不可用，凭证将保存到 %s（权限 0600）", _fallback_path())


def get_secret(name: str) -> str | None:
    env_name = ENV_FALLBACK.get(name)
    if _keyring_usable():
        try:
            import keyring

            value = keyring.get_password(SERVICE, name)
            if value:
                return value
        except Exception:  # pragma: no cover
            _warn_fallback()
    else:
        _warn_fallback()
    value = _read_file().get(name)
    if value:
        return value
    if env_name:
        return os.environ.get(env_name) or None
    return None


def set_secret(name: str, value: str) -> None:
    if _keyring_usable():
        try:
            import keyring

            keyring.set_password(SERVICE, name, value)
            return
        except Exception:  # pragma: no cover
            _warn_fallback()
    else:
        _warn_fallback()
    data = _read_file()
    data[name] = value
    _write_file(data)


def delete_secret(name: str) -> None:
    if _keyring_usable():
        try:
            import keyring

            keyring.delete_password(SERVICE, name)
        except Exception:  # pragma: no cover
            pass
    data = _read_file()
    if name in data:
        data.pop(name)
        _write_file(data)


def has_secret(name: str) -> bool:
    return bool(get_secret(name))
