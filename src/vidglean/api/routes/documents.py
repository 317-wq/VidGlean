"""文档：列表、详情、编辑、删除、重新生成、备注、AI 修改。"""

from __future__ import annotations

import difflib
import shutil
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Query

from vidglean import config
from vidglean.ai import client as ai_client
from vidglean.ai import prompts
from vidglean.api.common import (
    document_or_404,
    document_payload,
    ok,
    read_content,
    write_content,
)
from vidglean.api.schemas import (
    ApplyIn,
    AssistIn,
    ContentIn,
    NoteIn,
    PatchDocumentIn,
    RegenerateIn,
)
from vidglean.core.errors import AppError
from vidglean.pipeline import task_engine
from vidglean.store import repo

router = APIRouter(prefix="/api")


def _snippet(content: str, q: str, width: int = 60) -> str:
    if not q:
        return ""
    lowered = content.lower()
    index = lowered.find(q.lower())
    if index < 0:
        return ""
    start = max(0, index - width)
    end = min(len(content), index + len(q) + width)
    text = content[start:end].replace("\n", " ").strip()
    return f"{'…' if start else ''}{text}{'…' if end < len(content) else ''}"


@router.get("/documents")
async def list_documents(
    q: str | None = None,
    starred: bool | None = None,
    category: str | None = None,
    tag: str | None = None,
    content_type: str | None = None,
    platform: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    offset = (page - 1) * page_size
    items = repo.list_documents(
        q=q,
        starred=starred,
        category_id=category,
        tag=tag,
        content_type=content_type,
        platform=platform,
        limit=page_size,
        offset=offset,
    )
    total = repo.count_documents(
        q=q,
        starred=starred,
        category_id=category,
        tag=tag,
        content_type=content_type,
        platform=platform,
    )
    payload = []
    for document in items:
        entry = dict(document)
        entry["categories"] = document.get("categories") or []
        if q:
            entry["snippet"] = _snippet(read_content(document), q)
        else:
            entry.pop("file_path", None)
        payload.append(entry)
    return ok({"items": payload, "total": total, "page": page, "page_size": page_size})


@router.get("/documents/{doc_id}")
async def document_detail(doc_id: str) -> dict[str, Any]:
    document = document_or_404(doc_id)
    payload = document_payload(document)
    payload["note"] = repo.get_note(doc_id)
    payload["messages"] = repo.list_messages(doc_id)
    return ok(payload)


@router.put("/documents/{doc_id}/content")
async def save_content(doc_id: str, payload: ContentIn) -> dict[str, Any]:
    document = document_or_404(doc_id)
    previous = read_content(document)
    if payload.snapshot and previous.strip():
        repo.add_version(doc_id, previous, reason="edit")
    write_content(document, payload.content)
    return ok({"saved": True})


@router.patch("/documents/{doc_id}")
async def patch_document(doc_id: str, payload: PatchDocumentIn) -> dict[str, Any]:
    document = document_or_404(doc_id)
    fields: dict[str, Any] = {}
    if payload.title is not None:
        fields["title"] = payload.title.strip() or document["title"]
    if payload.starred is not None:
        fields["starred"] = 1 if payload.starred else 0
    if payload.content_type is not None:
        fields["content_type"] = payload.content_type
    if fields:
        repo.update_document(doc_id, **fields)
    if payload.tags is not None:
        repo.set_document_tags(doc_id, payload.tags)
    if payload.categories is not None:
        repo.set_document_categories(doc_id, payload.categories)
    document = repo.get_document(doc_id) or document
    content = read_content(document)
    repo.index_document(doc_id, document["title"], content, repo.tags_of(doc_id))
    return ok(document_payload(document))


@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: str) -> dict[str, Any]:
    document = document_or_404(doc_id)
    path = Path(document.get("file_path") or config.documents_dir() / f"{doc_id}.md")
    if path.exists():
        try:
            from send2trash import send2trash

            send2trash(str(path))
        except Exception:
            trash = config.documents_dir() / ".trash"
            trash.mkdir(parents=True, exist_ok=True)
            shutil.move(str(path), str(trash / path.name))
    subtitle_path = config.subtitles_dir() / f"{document['platform']}-{document['video_id']}.json"
    if subtitle_path.exists():
        subtitle_path.unlink()
    repo.delete_document(doc_id)
    return ok({"deleted": True})


@router.post("/documents/{doc_id}/regenerate")
async def regenerate(doc_id: str, payload: RegenerateIn) -> dict[str, Any]:
    document = document_or_404(doc_id)
    task_id = repo.create_task(
        source_url=document["source_url"],
        platform=document["platform"],
        video_id=document["video_id"],
        document_id=doc_id,
        options={
            "depth": payload.depth or document["summary_depth"],
            "template_id": payload.template_id or document["template_id"],
            "extra": payload.extra or "",
            "source": "regenerate",
        },
    )
    task_engine.notify()
    return ok({"task_id": task_id})


@router.post("/documents/{doc_id}/version/restore")
async def restore_version(doc_id: str) -> dict[str, Any]:
    document = document_or_404(doc_id)
    version = repo.pop_version(doc_id)
    if version is None:
        raise AppError("NOT_FOUND", "没有可恢复的版本", status=404)
    current = read_content(document)
    write_content(document, version["content"])
    repo.add_version(doc_id, current, reason="restore")
    return ok({"restored": True})


@router.get("/documents/{doc_id}/note")
async def get_note(doc_id: str) -> dict[str, Any]:
    document_or_404(doc_id)
    return ok({"content": repo.get_note(doc_id)})


@router.put("/documents/{doc_id}/note")
async def save_note(doc_id: str, payload: NoteIn) -> dict[str, Any]:
    document_or_404(doc_id)
    repo.set_note(doc_id, payload.content)
    return ok({"saved": True})


@router.post("/documents/{doc_id}/assist")
async def assist(doc_id: str, payload: AssistIn) -> dict[str, Any]:
    document = document_or_404(doc_id)
    model = repo.current_model()
    if model is None:
        raise AppError("API_KEY_INVALID", "请先在设置中添加一个 AI 模型")
    instruction = payload.instruction.strip()
    if not instruction:
        raise AppError("CONFLICT", "修改要求不能为空")
    before = read_content(document)
    text, usage = await ai_client.complete(
        model, prompts.assist_prompt(before, instruction), temperature=0.3
    )
    after = text.strip()
    if not after:
        raise AppError("API_ERROR", "模型返回了空内容")
    repo.add_usage(
        kind="assist",
        model_id=model["id"],
        document_id=doc_id,
        prompt_tokens=usage["prompt_tokens"],
        completion_tokens=usage["completion_tokens"],
    )
    diff = "\n".join(
        difflib.unified_diff(
            before.splitlines(), after.splitlines(), fromfile="当前版本", tofile="修改后", lineterm=""
        )
    )
    return ok({"before": before, "after": after, "diff": diff})


@router.post("/documents/{doc_id}/assist/apply")
async def apply_assist(doc_id: str, payload: ApplyIn) -> dict[str, Any]:
    document = document_or_404(doc_id)
    previous = read_content(document)
    if previous.strip():
        repo.add_version(doc_id, previous, reason="assist")
    write_content(document, payload.content)
    return ok({"applied": True})
