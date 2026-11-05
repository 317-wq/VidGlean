"""路径、默认配置与数据目录迁移。"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any

APP_DIR_NAME = "VidGlean"

DEFAULT_SETTINGS: dict[str, Any] = {
    "theme": "light",
    "depth": "auto",
    "template_id": "",
    "concurrency_video": 2,
    "concurrency_ai": 2,
    "max_retries": 3,
    "log_retention_days": 30,
    "notify": True,
    "update_url": "",
}


def base_dir() -> Path:
    """默认数据根目录（不含用户自定义位置）。"""
    env = os.environ.get("VIDGLEAN_BASE_DIR")
    if env:
        return Path(env).expanduser().resolve()
    if os.name == "nt":
        root = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
    else:
        root = Path(os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share"))
    return root / APP_DIR_NAME


def _location_file() -> Path:
    return base_dir() / "location.json"


def data_root() -> Path:
    """实际数据目录：环境变量 > 用户设置 > 默认目录。"""
    env = os.environ.get("VIDGLEAN_HOME")
    if env:
        return Path(env).expanduser().resolve()
    location = _location_file()
    if location.exists():
        try:
            raw = json.loads(location.read_text("utf-8"))
            value = raw.get("data_dir")
            if value:
                return Path(value).expanduser().resolve()
        except (OSError, ValueError):
            pass
    return base_dir()


def documents_dir() -> Path:
    return data_root() / "documents"


def subtitles_dir() -> Path:
    return data_root() / "subtitles"


def tasks_dir() -> Path:
    return data_root() / "tasks"


def templates_dir() -> Path:
    return data_root() / "templates"


def logs_dir() -> Path:
    return data_root() / "logs"


def tmp_dir() -> Path:
    return data_root() / "tmp"


def db_path() -> Path:
    return data_root() / "vidglean.db"


def ensure_dirs() -> None:
    for path in (
        data_root(),
        documents_dir(),
        subtitles_dir(),
        tasks_dir(),
        templates_dir(),
        logs_dir(),
        tmp_dir(),
    ):
        path.mkdir(parents=True, exist_ok=True)


def task_dir(task_id: str) -> Path:
    path = tasks_dir() / task_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def migrate_data_root(target: Path) -> Path:
    """把当前数据目录复制到新位置，并写入位置文件。

    旧目录保留（PRD 13.2 要求迁移成功后再处理旧数据，这里交给用户手动删除）。
    调用方必须在迁移前后关闭并重开数据库连接。
    """
    ensure_dirs()
    source = data_root()
    target = Path(target).expanduser().resolve()
    if target == source:
        return target
    target.mkdir(parents=True, exist_ok=True)
    for item in source.iterdir():
        if item.name == "location.json":
            continue
        destination = target / item.name
        if item.is_dir():
            shutil.copytree(item, destination, dirs_exist_ok=True)
        else:
            shutil.copy2(item, destination)
    _location_file().parent.mkdir(parents=True, exist_ok=True)
    _location_file().write_text(json.dumps({"data_dir": str(target)}, ensure_ascii=False), "utf-8")
    return target


def applied_settings(rows: dict[str, str]) -> dict[str, Any]:
    """把数据库里的字符串设置合并到默认值上，并做类型归一。"""
    settings = dict(DEFAULT_SETTINGS)
    for key, value in rows.items():
        if key not in DEFAULT_SETTINGS:
            continue
        default = DEFAULT_SETTINGS[key]
        if isinstance(default, bool):
            settings[key] = value in ("1", "true", "True")
        elif isinstance(default, int):
            try:
                settings[key] = int(value)
            except ValueError:
                settings[key] = default
        else:
            settings[key] = value
    return settings
