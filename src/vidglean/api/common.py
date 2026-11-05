"""路由共用的辅助函数。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from vidglean import config
from vidglean.core.errors import AppError
from vidglean.markdown_render import render
from vidglean.store import repo


def ok(data: Any = None) -> dict[str, Any]:
    return {"ok": True, "data": data}


def document_or_404(doc_id: str) -> dict[str, Any]:
    document = repo.get_document(doc_id)
    if document is None:
        raise AppError("NOT_FOUND", "文档不存在", status=404)
    return document


def read_content(document: dict[str, Any]) -> str:
    path = Path(document.get("file_path") or "")
    if not document.get("file_path"):
        path = config.documents_dir() / f"{document['id']}.md"
    try:
        return path.read_text("utf-8")
    except OSError:
        return ""


def write_content(document: dict[str, Any], content: str) -> str:
    path = Path(document.get("file_path") or "") or config.documents_dir() / f"{document['id']}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, "utf-8")
    tmp.replace(path)
    stat = path.stat()
    repo.update_document(document["id"], file_path=str(path), file_mtime=stat.st_mtime)
    repo.index_document(document["id"], document.get("title", ""), content, repo.tags_of(document["id"]))
    return str(path)


def document_payload(document: dict[str, Any], *, with_content: bool = True) -> dict[str, Any]:
    payload = dict(document)
    if with_content:
        content = read_content(document)
        payload["content"] = content
        payload["html"] = render(content)
    else:
        payload.setdefault("content", "")
    payload["has_previous_version"] = repo.last_version(document["id"]) is not None
    return payload
