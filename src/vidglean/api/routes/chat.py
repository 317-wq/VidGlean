"""文档专属 AI 对话（SSE 流式）。"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from vidglean import config
from vidglean.ai import client as ai_client
from vidglean.ai import prompts
from vidglean.api.common import document_or_404, ok, read_content
from vidglean.api.schemas import ChatIn
from vidglean.core.errors import AppError, from_exception
from vidglean.store import repo

router = APIRouter(prefix="/api")

MAX_HISTORY = 12


def _subtitle_text(document: dict[str, Any]) -> str:
    path = config.subtitles_dir() / f"{document['platform']}-{document['video_id']}.json"
    if not path.exists():
        return ""
    try:
        payload = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return ""
    return str(payload.get("text") or "")


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.get("/documents/{doc_id}/messages")
async def list_messages(doc_id: str) -> dict[str, Any]:
    document_or_404(doc_id)
    return ok({"items": repo.list_messages(doc_id)})


@router.delete("/documents/{doc_id}/messages")
async def clear_messages(doc_id: str) -> dict[str, Any]:
    document_or_404(doc_id)
    repo.clear_messages(doc_id)
    return ok({"cleared": True})


@router.post("/documents/{doc_id}/chat")
async def chat(doc_id: str, payload: ChatIn) -> StreamingResponse:
    document = document_or_404(doc_id)
    model = repo.current_model()
    if model is None:
        raise AppError("API_KEY_INVALID", "请先在设置中添加一个 AI 模型")
    message = payload.message.strip()
    if not message:
        raise AppError("CONFLICT", "消息不能为空")

    content = read_content(document)
    subtitle = _subtitle_text(document)

    async def generator():
        repo.add_message(doc_id, "user", message)
        history = repo.list_messages(doc_id)[-MAX_HISTORY:]
        messages = [{"role": "system", "content": prompts.chat_system(content, subtitle)}]
        messages += [
            {"role": item["role"], "content": item["content"]}
            for item in history
            if item["role"] in ("user", "assistant")
        ]
        buffer: list[str] = []
        usage: dict[str, int] | None = None
        try:
            async for delta, chunk_usage in ai_client.stream(model, messages):
                if chunk_usage:
                    usage = chunk_usage
                if delta:
                    buffer.append(delta)
                    yield _sse("delta", {"text": delta})
        except Exception as exc:  # 包括 AppError 与网络异常
            error = from_exception(exc)
            yield _sse("error", error.to_dict())
            return
        text = "".join(buffer).strip()
        if text:
            repo.add_message(doc_id, "assistant", text)
        if usage:
            repo.add_usage(
                kind="chat",
                model_id=model["id"],
                document_id=doc_id,
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
            )
        yield _sse("done", {"content": text})

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
