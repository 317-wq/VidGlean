"""数据访问层：所有 SQL 集中在这里，API 与任务引擎只调用函数。"""

from __future__ import annotations

import json
import uuid
from typing import Any

from vidglean import config
from vidglean.core.models import StageName, TaskStatus
from vidglean.core.utils import now_iso
from vidglean.store import db, search

SEPARATOR = "\u001f"


def _new_id() -> str:
    return uuid.uuid4().hex


def _row(row: Any) -> dict[str, Any] | None:
    return None if row is None else dict(row)


def _rows(rows: list[Any]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


# ---------------------------------------------------------------- settings


def get_settings() -> dict[str, Any]:
    rows = db.query_all("SELECT key, value FROM settings")
    return config.applied_settings({row["key"]: row["value"] for row in rows})


def set_setting(key: str, value: Any) -> None:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    db.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, text),
    )


def set_settings(values: dict[str, Any]) -> None:
    for key, value in values.items():
        if key in config.DEFAULT_SETTINGS:
            set_setting(key, value)


# ---------------------------------------------------------------- documents


_COLUMNS = (
    "platform",
    "video_id",
    "title",
    "author",
    "cover_url",
    "duration",
    "source_url",
    "content_type",
    "summary_depth",
    "template_id",
    "file_path",
    "status",
)


def create_document(**fields: Any) -> str:
    doc_id = _new_id()
    stamp = now_iso()
    values = {key: fields.get(key, "") for key in _COLUMNS}
    values["duration"] = int(fields.get("duration") or 0)
    values["status"] = fields.get("status") or "ready"
    db.execute(
        "INSERT INTO documents (id, platform, video_id, title, author, cover_url, duration, "
        "source_url, content_type, summary_depth, template_id, file_path, status, "
        "created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            doc_id,
            values["platform"],
            values["video_id"],
            values["title"],
            values["author"],
            values["cover_url"],
            values["duration"],
            values["source_url"],
            values["content_type"] or "其他",
            values["summary_depth"] or "standard",
            values["template_id"],
            values["file_path"],
            values["status"],
            stamp,
            stamp,
        ),
    )
    return doc_id


_DOC_FIELDS = {
    "title",
    "author",
    "cover_url",
    "duration",
    "source_url",
    "content_type",
    "summary_depth",
    "template_id",
    "file_path",
    "file_mtime",
    "status",
    "starred",
    "video_id",
    "platform",
}


def update_document(doc_id: str, **fields: Any) -> None:
    updates = {k: v for k, v in fields.items() if k in _DOC_FIELDS}
    if not updates:
        return
    updates["updated_at"] = now_iso()
    assignments = ", ".join(f"{key} = ?" for key in updates)
    db.execute(
        f"UPDATE documents SET {assignments} WHERE id = ?",
        (*updates.values(), doc_id),
    )


_DOC_ONE = (
    "SELECT d.*, "
    "(SELECT group_concat(t.name, char(31)) FROM document_tags dt JOIN tags t ON t.id = dt.tag_id "
    " WHERE dt.document_id = d.id) AS tag_names "
    "FROM documents d WHERE d.id = ?"
)


def get_document(doc_id: str) -> dict[str, Any] | None:
    document = _row(db.query_one(_DOC_ONE, (doc_id,)))
    if document is None:
        return None
    document["tags"] = [t for t in (document.pop("tag_names") or "").split(SEPARATOR) if t]
    document["categories"] = _category_ids(doc_id)
    return document


def find_document(platform: str, video_id: str) -> dict[str, Any] | None:
    return _row(
        db.query_one(
            "SELECT * FROM documents WHERE platform = ? AND video_id = ?", (platform, video_id)
        )
    )


def _build_filters(
    *,
    q: str | None,
    starred: bool | None,
    category_id: str | None,
    tag: str | None,
    content_type: str | None,
    platform: str | None,
) -> tuple[str, list[Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if q:
        ids = search_ids(q)
        if not ids:
            return " WHERE 1 = 0", []
        clauses.append(f"d.id IN ({','.join('?' * len(ids))})")
        params.extend(ids)
    if starred is not None:
        clauses.append("d.starred = ?")
        params.append(1 if starred else 0)
    if category_id:
        clauses.append("EXISTS (SELECT 1 FROM document_categories c WHERE c.document_id = d.id AND c.category_id = ?)")
        params.append(category_id)
    if tag:
        clauses.append("EXISTS (SELECT 1 FROM document_tags dt JOIN tags t ON t.id = dt.tag_id WHERE dt.document_id = d.id AND t.name = ?)")
        params.append(tag)
    if content_type:
        clauses.append("d.content_type = ?")
        params.append(content_type)
    if platform:
        clauses.append("d.platform = ?")
        params.append(platform)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, params


_DOC_SELECT = (
    "SELECT d.*, "
    "(SELECT group_concat(t.name, char(31)) FROM document_tags dt JOIN tags t ON t.id = dt.tag_id "
    " WHERE dt.document_id = d.id) AS tag_names "
    "FROM documents d"
)


def list_documents(
    *,
    q: str | None = None,
    starred: bool | None = None,
    category_id: str | None = None,
    tag: str | None = None,
    content_type: str | None = None,
    platform: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    where, params = _build_filters(
        q=q,
        starred=starred,
        category_id=category_id,
        tag=tag,
        content_type=content_type,
        platform=platform,
    )
    rows = db.query_all(
        f"{_DOC_SELECT}{where} ORDER BY d.created_at DESC LIMIT ? OFFSET ?",
        (*params, limit, offset),
    )
    documents = _rows(rows)
    for document in documents:
        document["tags"] = [t for t in (document.pop("tag_names") or "").split(SEPARATOR) if t]
    return documents


def count_documents(
    *,
    q: str | None = None,
    starred: bool | None = None,
    category_id: str | None = None,
    tag: str | None = None,
    content_type: str | None = None,
    platform: str | None = None,
) -> int:
    where, params = _build_filters(
        q=q,
        starred=starred,
        category_id=category_id,
        tag=tag,
        content_type=content_type,
        platform=platform,
    )
    return int(db.scalar(f"SELECT COUNT(*) FROM documents d{where}", params) or 0)


def delete_document(doc_id: str) -> None:
    for table in (
        "document_tags",
        "document_categories",
        "notes",
        "messages",
        "doc_versions",
    ):
        db.execute(f"DELETE FROM {table} WHERE document_id = ?", (doc_id,))
    # 文档没了，挂在它上面的任务记录也不再有意义
    db.execute(
        "DELETE FROM task_stages WHERE task_id IN (SELECT id FROM tasks WHERE document_id = ?)",
        (doc_id,),
    )
    db.execute("DELETE FROM tasks WHERE document_id = ?", (doc_id,))
    db.execute("DELETE FROM documents_fts WHERE doc_id = ?", (doc_id,))
    db.execute("DELETE FROM documents WHERE id = ?", (doc_id,))


# ---------------------------------------------------------------- 分类与标签


def _category_ids(doc_id: str) -> list[str]:
    rows = db.query_all("SELECT category_id FROM document_categories WHERE document_id = ?", (doc_id,))
    return [row["category_id"] for row in rows]


def list_categories() -> list[dict[str, Any]]:
    rows = db.query_all(
        "SELECT c.*, (SELECT COUNT(*) FROM document_categories dc WHERE dc.category_id = c.id) AS count "
        "FROM categories c ORDER BY c.created_at"
    )
    return _rows(rows)


def create_category(name: str) -> dict[str, Any]:
    existing = db.query_one("SELECT * FROM categories WHERE name = ?", (name,))
    if existing:
        return dict(existing)
    category_id = _new_id()
    db.execute(
        "INSERT INTO categories (id, name, created_at) VALUES (?,?,?)",
        (category_id, name, now_iso()),
    )
    return dict(db.query_one("SELECT * FROM categories WHERE id = ?", (category_id,)))


def rename_category(category_id: str, name: str) -> None:
    db.execute("UPDATE categories SET name = ? WHERE id = ?", (name, category_id))


def delete_category(category_id: str) -> None:
    db.execute("DELETE FROM document_categories WHERE category_id = ?", (category_id,))
    db.execute("DELETE FROM categories WHERE id = ?", (category_id,))


def set_document_categories(doc_id: str, category_ids: list[str]) -> None:
    db.execute("DELETE FROM document_categories WHERE document_id = ?", (doc_id,))
    for category_id in category_ids:
        db.execute(
            "INSERT OR IGNORE INTO document_categories (document_id, category_id) VALUES (?,?)",
            (doc_id, category_id),
        )


def list_tags() -> list[dict[str, Any]]:
    rows = db.query_all(
        "SELECT t.*, (SELECT COUNT(*) FROM document_tags dt WHERE dt.tag_id = t.id) AS count "
        "FROM tags t ORDER BY count DESC, t.name"
    )
    return _rows(rows)


def _ensure_tag(name: str) -> str:
    row = db.query_one("SELECT id FROM tags WHERE name = ?", (name,))
    if row:
        return row["id"]
    tag_id = _new_id()
    db.execute("INSERT INTO tags (id, name) VALUES (?,?)", (tag_id, name))
    return tag_id


def set_document_tags(doc_id: str, names: list[str]) -> None:
    db.execute("DELETE FROM document_tags WHERE document_id = ?", (doc_id,))
    seen: set[str] = set()
    for raw in names:
        name = raw.strip()
        if not name or name in seen:
            continue
        seen.add(name)
        tag_id = _ensure_tag(name)
        db.execute(
            "INSERT OR IGNORE INTO document_tags (document_id, tag_id) VALUES (?,?)",
            (doc_id, tag_id),
        )


def tags_of(doc_id: str) -> list[str]:
    rows = db.query_all(
        "SELECT t.name FROM document_tags dt JOIN tags t ON t.id = dt.tag_id "
        "WHERE dt.document_id = ? ORDER BY t.name",
        (doc_id,),
    )
    return [row["name"] for row in rows]


# ---------------------------------------------------------------- 备注


def get_note(doc_id: str) -> str:
    row = db.query_one("SELECT content FROM notes WHERE document_id = ?", (doc_id,))
    return row["content"] if row else ""


def set_note(doc_id: str, content: str) -> None:
    db.execute(
        "INSERT INTO notes (document_id, content, updated_at) VALUES (?,?,?) "
        "ON CONFLICT(document_id) DO UPDATE SET content = excluded.content, updated_at = excluded.updated_at",
        (doc_id, content, now_iso()),
    )


# ---------------------------------------------------------------- 对话


def list_messages(doc_id: str) -> list[dict[str, Any]]:
    rows = db.query_all(
        "SELECT * FROM messages WHERE document_id = ? ORDER BY created_at, rowid", (doc_id,)
    )
    return _rows(rows)


def add_message(doc_id: str, role: str, content: str) -> dict[str, Any]:
    message_id = _new_id()
    stamp = now_iso()
    db.execute(
        "INSERT INTO messages (id, document_id, role, content, created_at) VALUES (?,?,?,?,?)",
        (message_id, doc_id, role, content, stamp),
    )
    return {"id": message_id, "document_id": doc_id, "role": role, "content": content, "created_at": stamp}


def clear_messages(doc_id: str) -> None:
    db.execute("DELETE FROM messages WHERE document_id = ?", (doc_id,))


# ---------------------------------------------------------------- 文档版本


def add_version(doc_id: str, content: str, reason: str = "") -> None:
    db.execute(
        "INSERT INTO doc_versions (id, document_id, content, reason, created_at) VALUES (?,?,?,?,?)",
        (_new_id(), doc_id, content, reason, now_iso()),
    )


def last_version(doc_id: str) -> dict[str, Any] | None:
    return _row(
        db.query_one(
            "SELECT * FROM doc_versions WHERE document_id = ? ORDER BY created_at DESC, rowid DESC LIMIT 1",
            (doc_id,),
        )
    )


def pop_version(doc_id: str) -> dict[str, Any] | None:
    version = last_version(doc_id)
    if version:
        db.execute("DELETE FROM doc_versions WHERE id = ?", (version["id"],))
    return version


# ---------------------------------------------------------------- 任务


def create_task(
    *,
    source_url: str,
    options: dict[str, Any] | None = None,
    platform: str = "bilibili",
    document_id: str | None = None,
    video_id: str = "",
) -> str:
    task_id = _new_id()
    stamp = now_iso()
    db.execute(
        "INSERT INTO tasks (id, document_id, source_url, platform, video_id, status, current_stage, "
        "retry_count, options, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (
            task_id,
            document_id,
            source_url,
            platform,
            video_id,
            TaskStatus.PENDING,
            "",
            0,
            json.dumps(options or {}, ensure_ascii=False),
            stamp,
            stamp,
        ),
    )
    for stage in StageName.ORDER:
        db.execute(
            "INSERT INTO task_stages (task_id, stage, status) VALUES (?,?,?)",
            (task_id, stage, "pending"),
        )
    return task_id


_TASK_FIELDS = {
    "status",
    "current_stage",
    "retry_count",
    "next_retry_at",
    "error_code",
    "error_message",
    "document_id",
    "video_id",
    "options",
}


def update_task(task_id: str, **fields: Any) -> None:
    updates = {k: v for k, v in fields.items() if k in _TASK_FIELDS}
    if not updates:
        return
    if "options" in updates and not isinstance(updates["options"], str):
        updates["options"] = json.dumps(updates["options"], ensure_ascii=False)
    updates["updated_at"] = now_iso()
    assignments = ", ".join(f"{key} = ?" for key in updates)
    db.execute(f"UPDATE tasks SET {assignments} WHERE id = ?", (*updates.values(), task_id))


def get_task(task_id: str) -> dict[str, Any] | None:
    task = _row(db.query_one("SELECT * FROM tasks WHERE id = ?", (task_id,)))
    if task is None:
        return None
    task["options"] = json.loads(task.get("options") or "{}")
    return task


def list_tasks(
    status: str | None = None, limit: int = 100, include_done: bool = False
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if status:
        clauses.append("t.status = ?")
        params.append(status)
    elif not include_done:
        # 默认只列还有事的任务；已完成/已取消不再占版面
        clauses.append("t.status NOT IN ('succeeded', 'canceled')")
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    rows = db.query_all(
        "SELECT t.*, d.title AS document_title FROM tasks t "
        f"LEFT JOIN documents d ON d.id = t.document_id{where} "
        "ORDER BY t.created_at DESC LIMIT ?",
        (*params, limit),
    )
    tasks = _rows(rows)
    for task in tasks:
        task["options"] = json.loads(task.get("options") or "{}")
    return tasks


def delete_finished_tasks() -> int:
    """清掉已完成/已取消的任务记录，返回删除条数。"""
    rows = db.query_all("SELECT id FROM tasks WHERE status IN ('succeeded', 'canceled')")
    for row in rows:
        db.execute("DELETE FROM task_stages WHERE task_id = ?", (row["id"],))
        db.execute("DELETE FROM tasks WHERE id = ?", (row["id"],))
    return len(rows)


def set_stage(
    task_id: str,
    stage: str,
    status: str,
    *,
    error_code: str = "",
    error_message: str = "",
) -> None:
    stamp = now_iso()
    existing = db.query_one("SELECT * FROM task_stages WHERE task_id = ? AND stage = ?", (task_id, stage))
    if existing is None:
        db.execute(
            "INSERT INTO task_stages (task_id, stage, status, error_code, error_message, started_at, finished_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (
                task_id,
                stage,
                status,
                error_code,
                error_message,
                stamp if status == "running" else None,
                stamp if status in ("succeeded", "failed", "skipped") else None,
            ),
        )
        return
    updates = ["status = ?", "error_code = ?", "error_message = ?"]
    params: list[Any] = [status, error_code, error_message]
    if status == "running":
        updates.append("started_at = ?")
        params.append(stamp)
    if status in ("succeeded", "failed", "skipped"):
        updates.append("finished_at = ?")
        params.append(stamp)
    params.extend([task_id, stage])
    db.execute(f"UPDATE task_stages SET {', '.join(updates)} WHERE task_id = ? AND stage = ?", params)


def get_stages(task_id: str) -> list[dict[str, Any]]:
    return _rows(
        db.query_all(
            "SELECT * FROM task_stages WHERE task_id = ? "
            "ORDER BY CASE stage WHEN 'link_parse' THEN 1 WHEN 'subtitle' THEN 2 WHEN 'ai_analyze' THEN 3 ELSE 4 END",
            (task_id,),
        )
    )


def reset_stages(task_id: str, from_stage: str) -> None:
    """把 from_stage 及其之后的阶段重置为 pending。"""
    start = StageName.ORDER.index(from_stage)
    for stage in StageName.ORDER[start:]:
        set_stage(task_id, stage, "pending")


def mark_running_interrupted() -> int:
    rows = db.query_all("SELECT id FROM tasks WHERE status = ?", (TaskStatus.RUNNING,))
    for row in rows:
        update_task(row["id"], status=TaskStatus.INTERRUPTED, next_retry_at=None)
    return len(rows)


def due_retry_ids(now: str) -> list[str]:
    rows = db.query_all(
        "SELECT id FROM tasks WHERE status = ? AND next_retry_at IS NOT NULL AND next_retry_at <= ? "
        "ORDER BY next_retry_at",
        (TaskStatus.FAILED, now),
    )
    return [row["id"] for row in rows]


def pending_task_ids() -> list[str]:
    rows = db.query_all(
        "SELECT id FROM tasks WHERE status = ? ORDER BY created_at", (TaskStatus.PENDING,)
    )
    return [row["id"] for row in rows]


# ---------------------------------------------------------------- 模型配置


def list_models() -> list[dict[str, Any]]:
    return _rows(db.query_all("SELECT * FROM models ORDER BY created_at"))


def get_model(model_id: str) -> dict[str, Any] | None:
    return _row(db.query_one("SELECT * FROM models WHERE id = ?", (model_id,)))


def current_model() -> dict[str, Any] | None:
    return _row(db.query_one("SELECT * FROM models WHERE is_current = 1 LIMIT 1"))


def create_model(**fields: Any) -> str:
    model_id = _new_id()
    db.execute(
        "INSERT INTO models (id, name, base_url, model, temperature, max_tokens, timeout, is_current, created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (
            model_id,
            fields["name"],
            fields["base_url"],
            fields["model"],
            float(fields.get("temperature", 0.5)),
            int(fields.get("max_tokens", 8192)),
            int(fields.get("timeout", 120)),
            0,
            now_iso(),
        ),
    )
    if db.scalar("SELECT COUNT(*) FROM models") == 1:
        set_current_model(model_id)
    return model_id


def update_model(model_id: str, **fields: Any) -> None:
    allowed = {"name", "base_url", "model", "temperature", "max_tokens", "timeout"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return
    assignments = ", ".join(f"{key} = ?" for key in updates)
    db.execute(f"UPDATE models SET {assignments} WHERE id = ?", (*updates.values(), model_id))


def delete_model(model_id: str) -> None:
    db.execute("DELETE FROM models WHERE id = ?", (model_id,))
    row = db.query_one("SELECT id FROM models ORDER BY created_at LIMIT 1")
    if row and not db.query_one("SELECT id FROM models WHERE is_current = 1"):
        set_current_model(row["id"])


def set_current_model(model_id: str) -> None:
    db.execute("UPDATE models SET is_current = 0")
    db.execute("UPDATE models SET is_current = 1 WHERE id = ?", (model_id,))


# ---------------------------------------------------------------- 模板


def list_templates() -> list[dict[str, Any]]:
    return _rows(db.query_all("SELECT * FROM templates ORDER BY kind, created_at"))


def get_template(template_id: str) -> dict[str, Any] | None:
    return _row(db.query_one("SELECT * FROM templates WHERE id = ?", (template_id,)))


def find_template_by_name(name: str) -> dict[str, Any] | None:
    return _row(db.query_one("SELECT * FROM templates WHERE name = ?", (name,)))


def default_template() -> dict[str, Any] | None:
    return _row(db.query_one("SELECT * FROM templates WHERE is_default = 1 LIMIT 1"))


def set_default_template(template_id: str) -> None:
    db.execute("UPDATE templates SET is_default = 0")
    db.execute("UPDATE templates SET is_default = 1 WHERE id = ?", (template_id,))


def create_template(
    *, name: str, kind: str = "custom", description: str = "", path: str = ""
) -> str:
    template_id = _new_id()
    db.execute(
        "INSERT INTO templates (id, name, kind, description, path, is_default, created_at) "
        "VALUES (?,?,?,?,?,0,?)",
        (template_id, name, kind, description, path, now_iso()),
    )
    return template_id


def delete_template(template_id: str) -> None:
    db.execute("DELETE FROM templates WHERE id = ?", (template_id,))


# ---------------------------------------------------------------- 用量


def add_usage(
    *,
    kind: str,
    model_id: str = "",
    document_id: str | None = None,
    task_id: str | None = None,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    estimated_cost: float = 0.0,
) -> None:
    total = int(prompt_tokens or 0) + int(completion_tokens or 0)
    db.execute(
        "INSERT INTO usage_log (id, document_id, task_id, kind, model_id, prompt_tokens, "
        "completion_tokens, total_tokens, estimated_cost, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (
            _new_id(),
            document_id,
            task_id,
            kind,
            model_id,
            int(prompt_tokens or 0),
            int(completion_tokens or 0),
            total,
            float(estimated_cost or 0.0),
            now_iso(),
        ),
    )


def usage_summary(days: int = 30) -> dict[str, Any]:
    rows = db.query_all(
        "SELECT substr(created_at, 1, 10) AS day, kind, COUNT(*) AS calls, "
        "SUM(prompt_tokens) AS prompt_tokens, SUM(completion_tokens) AS completion_tokens, "
        "SUM(total_tokens) AS total_tokens, SUM(estimated_cost) AS cost "
        "FROM usage_log WHERE created_at >= date('now', ?) GROUP BY day, kind ORDER BY day DESC",
        (f"-{int(days)} day",),
    )
    totals = db.query_one(
        "SELECT COUNT(*) AS calls, COALESCE(SUM(total_tokens),0) AS total_tokens, "
        "COALESCE(SUM(estimated_cost),0) AS cost FROM usage_log"
    )
    return {
        "daily": _rows(rows),
        "totals": dict(totals) if totals else {"calls": 0, "total_tokens": 0, "cost": 0},
    }


def recent_usage(limit: int = 50) -> list[dict[str, Any]]:
    return _rows(
        db.query_all("SELECT * FROM usage_log ORDER BY created_at DESC LIMIT ?", (limit,))
    )


# ---------------------------------------------------------------- 全文索引


def index_document(doc_id: str, title: str, body: str, tags: list[str]) -> None:
    db.execute("DELETE FROM documents_fts WHERE doc_id = ?", (doc_id,))
    db.execute(
        "INSERT INTO documents_fts (doc_id, title, body, tags) VALUES (?,?,?,?)",
        (
            doc_id,
            search.tokenize(title),
            search.tokenize(body),
            search.tokenize(" ".join(tags)),
        ),
    )


def search_ids(q: str) -> list[str]:
    if not q.strip():
        return []
    if search.needs_like_fallback(q):
        pattern = f"%{q.strip()}%"
        rows = db.query_all(
            "SELECT doc_id FROM documents_fts WHERE body LIKE ? OR title LIKE ?", (pattern, pattern)
        )
        return [row["doc_id"] for row in rows]
    expression = search.match_expression(q)
    if not expression:
        return []
    try:
        rows = db.query_all(
            "SELECT doc_id FROM documents_fts WHERE documents_fts MATCH ?", (expression,)
        )
    except Exception:
        return []
    return [row["doc_id"] for row in rows]
