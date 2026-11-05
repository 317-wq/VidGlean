"""SQLite 连接与薄封装。

单进程单用户，全部访问走同一连接；写操作立即提交，读操作加锁，保证
事件循环与后台线程混用时不出现「连接被并发使用」的问题。
"""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterable, Sequence
from typing import Any

from vidglean import config
from vidglean.store.migrations import MIGRATIONS

_conn: sqlite3.Connection | None = None
_lock = threading.RLock()


def get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        config.ensure_dirs()
        _conn = sqlite3.connect(config.db_path(), check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.execute("PRAGMA synchronous=NORMAL")
        _conn.execute("PRAGMA foreign_keys=ON")
    return _conn


def init_db() -> None:
    conn = get_conn()
    with _lock:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        for index, script in enumerate(MIGRATIONS, start=1):
            if index > version:
                conn.executescript(script)
                conn.execute(f"PRAGMA user_version={index}")
                conn.commit()


def close_db() -> None:
    global _conn
    with _lock:
        if _conn is not None:
            _conn.close()
            _conn = None


def execute(sql: str, params: Sequence[Any] = ()) -> sqlite3.Cursor:
    conn = get_conn()
    with _lock:
        cursor = conn.execute(sql, params)
        conn.commit()
        return cursor


def executemany(sql: str, rows: Iterable[Sequence[Any]]) -> None:
    conn = get_conn()
    with _lock:
        conn.executemany(sql, rows)
        conn.commit()


def query_all(sql: str, params: Sequence[Any] = ()) -> list[sqlite3.Row]:
    conn = get_conn()
    with _lock:
        return list(conn.execute(sql, params).fetchall())


def query_one(sql: str, params: Sequence[Any] = ()) -> sqlite3.Row | None:
    conn = get_conn()
    with _lock:
        return conn.execute(sql, params).fetchone()


def scalar(sql: str, params: Sequence[Any] = ()) -> Any:
    row = query_one(sql, params)
    return None if row is None else row[0]
