"""导入：链接预览与创建任务。"""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter

from vidglean import platforms
from vidglean.api.common import ok
from vidglean.api.schemas import ImportIn, PreviewIn
from vidglean.core.errors import AppError
from vidglean.core.models import ContentType
from vidglean.core.utils import fmt_duration
from vidglean.pipeline import task_engine
from vidglean.store import repo

router = APIRouter(prefix="/api")

RECOMMEND = {
    ContentType.TECH: "builtin-tech",
    ContentType.OPINION: "builtin-opinion",
}

_SEM = asyncio.Semaphore(3)


def recommend_template(content_type: str) -> str:
    return RECOMMEND.get(content_type, "builtin-general")


async def _preview_one(url: str) -> dict[str, Any]:
    try:
        platform = platforms.detect(url)
        async with _SEM:
            video_id = await platform.extract_video_id(url)
            meta = await platform.fetch_meta(video_id)
        existing = repo.find_document(meta.platform, meta.video_id)
        return {
            "ok": True,
            "url": url,
            "platform": meta.platform,
            "video_id": meta.video_id,
            "title": meta.title,
            "author": meta.author,
            "cover_url": meta.cover_url,
            "duration": meta.duration,
            "duration_text": fmt_duration(meta.duration),
            "content_type": meta.content_type,
            "source_url": meta.source_url,
            "exists_document_id": existing["id"] if existing else "",
            "recommended_template_id": recommend_template(meta.content_type),
        }
    except AppError as error:
        return {"ok": False, "url": url, "error": error.to_dict()}
    except Exception as error:  # pragma: no cover - 网络异常兜底
        return {
            "ok": False,
            "url": url,
            "error": {"code": "UNKNOWN", "message": "解析失败", "detail": str(error)},
        }


@router.post("/import/preview")
async def preview(payload: PreviewIn) -> dict[str, Any]:
    urls: list[str] = []
    seen: set[str] = set()
    for raw in payload.urls:
        value = raw.strip()
        if value and value not in seen:
            seen.add(value)
            urls.append(value)
    if not urls:
        return ok({"items": []})
    items = await asyncio.gather(*(_preview_one(url) for url in urls[:20]))
    return ok({"items": list(items)})


@router.post("/import")
async def create_import(payload: ImportIn) -> dict[str, Any]:
    created: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for item in payload.items[:20]:
        url = item.url.strip()
        if not url:
            continue
        try:
            platform = platforms.detect(url)
            video_id = await platform.extract_video_id(url)
        except AppError as error:
            skipped.append({"url": url, "error": error.to_dict()})
            continue
        existing = repo.find_document(platform.__name__.split(".")[-1], video_id)
        if existing and not item.force:
            skipped.append(
                {
                    "url": url,
                    "document_id": existing["id"],
                    "error": {"code": "CONFLICT", "message": "该视频已有文档，可选择重新生成"},
                }
            )
            continue
        task_id = repo.create_task(
            source_url=url,
            platform="bilibili",
            video_id=video_id,
            document_id=existing["id"] if existing else None,
            options={
                "depth": item.depth,
                "template_id": item.template_id,
                "extra": item.extra,
                "source": "regenerate" if existing else "import",
            },
        )
        created.append({"task_id": task_id, "url": url})
    if created:
        task_engine.notify()
    return ok({"tasks": created, "skipped": skipped})
