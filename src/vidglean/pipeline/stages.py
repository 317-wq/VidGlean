"""任务阶段实现：链接解析 -> 字幕 -> AI 分析 -> Markdown 生成。"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from vidglean import config, platforms, templates_builtin
from vidglean.ai.summarize import extract_tags, summarize
from vidglean.core.errors import AppError
from vidglean.core.events import bus
from vidglean.core.models import StageName
from vidglean.core.utils import fmt_duration, now_iso
from vidglean.store import repo


@dataclass
class TaskContext:
    task: dict[str, Any]
    workdir: Path
    meta: dict[str, Any] | None = None
    subtitle: dict[str, Any] | None = None
    summary: str = ""
    document_id: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def options(self) -> dict[str, Any]:
        return self.task.get("options") or {}

    def artifact(self, name: str) -> Path:
        return self.workdir / name


def _write_json(path: Path, payload: Any) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), "utf-8")
    os.replace(tmp, path)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text("utf-8"))


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, "utf-8")
    os.replace(tmp, path)


def _disable_proxy_for_bilibili() -> None:
    """部分开发机存在失效代理，避免影响平台请求。"""
    # 占位：如需强制直连，可在这里清理 httpx 的 trust_env 行为。
    return None


async def run_link_parse(ctx: TaskContext) -> None:
    _disable_proxy_for_bilibili()
    url = ctx.task["source_url"]
    platform = platforms.detect(url)
    video_id = await platform.extract_video_id(url)
    meta = await platform.fetch_meta(video_id)
    payload = meta.to_dict()
    payload["duration_text"] = fmt_duration(meta.duration)
    ctx.meta = payload
    _write_json(ctx.artifact("01_meta.json"), payload)
    repo.update_task(
        ctx.task["id"], video_id=meta.video_id, platform=meta.platform
    )


async def run_subtitle(ctx: TaskContext) -> None:
    meta = ctx.meta or _read_json(ctx.artifact("01_meta.json"))
    ctx.meta = meta
    platform = platforms.detect(meta.get("source_url") or ctx.task["source_url"])
    cache = config.subtitles_dir() / f"{meta['platform']}-{meta['video_id']}.json"
    if cache.exists():
        try:
            data = _read_json(cache)
        except (OSError, ValueError):
            data = None
    else:
        data = None
    if not data:
        cid = (meta.get("extra") or {}).get("cid")
        data = await platform.fetch_subtitle(meta["video_id"], cid)
        config.subtitles_dir().mkdir(parents=True, exist_ok=True)
        _write_json(cache, data)
    ctx.subtitle = data
    _write_json(ctx.artifact("02_subtitle.json"), data)


def _resolve_template(options: dict[str, Any]) -> str:
    settings = repo.get_settings()
    template_id = str(options.get("template_id") or settings.get("template_id") or "")
    row = repo.get_template(template_id) if template_id else None
    if row is None:
        row = repo.default_template()
    if row is None:
        row = repo.get_template("builtin-general")
    if row is None:
        raise AppError("BAD_TEMPLATE", "找不到可用的 Markdown 模板")
    text = templates_builtin.template_text(row)
    if not text.strip():
        raise AppError("BAD_TEMPLATE", "模板内容为空")
    return text


async def run_ai_analyze(ctx: TaskContext) -> None:
    meta = ctx.meta or _read_json(ctx.artifact("01_meta.json"))
    subtitle = ctx.subtitle or _read_json(ctx.artifact("02_subtitle.json"))
    ctx.meta = meta
    ctx.subtitle = subtitle
    model = repo.current_model()
    if model is None:
        raise AppError("API_KEY_INVALID", "请先在设置中添加一个 AI 模型")
    options = ctx.options
    depth = str(options.get("depth") or repo.get_settings().get("depth") or "auto")
    if depth == "auto":
        depth = "standard"
    template_text = _resolve_template(options)
    values = {
        "video_title": meta.get("title", ""),
        "author": meta.get("author", ""),
        "platform": "Bilibili",
        "url": meta.get("source_url", ""),
        "duration": meta.get("duration_text", ""),
        "date": now_iso()[:10],
        "content_type": meta.get("content_type", ""),
        "depth": depth,
        "extra": options.get("extra", ""),
        "transcript": "",
    }
    rendered_template = templates_builtin.render(template_text, values)
    result = await summarize(
        meta=meta,
        transcript=str(subtitle.get("text") or ""),
        template_text=rendered_template,
        depth=depth,
        extra=str(options.get("extra") or ""),
        model=model,
    )
    _write_text(ctx.artifact("03_summary.md"), result.text)
    ctx.summary = result.text
    repo.add_usage(
        kind="summary",
        model_id=model["id"],
        document_id=ctx.task.get("document_id"),
        task_id=ctx.task["id"],
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
    )


def _document_header(meta: dict[str, Any]) -> str:
    title = meta.get("title", "未命名视频")
    url = meta.get("source_url", "")
    author = meta.get("author", "")
    duration = meta.get("duration_text", "")
    content_type = meta.get("content_type", "")
    return (
        f"> **视频**：[{title}]({url})\n"
        f"> **UP 主**：{author}　**平台**：Bilibili　**时长**：{duration}　**类型**：{content_type}\n"
        f"> **生成时间**：{now_iso().replace('T', ' ')}\n\n---\n\n"
    )


async def run_render_md(ctx: TaskContext) -> None:
    meta = ctx.meta or _read_json(ctx.artifact("01_meta.json"))
    summary_path = ctx.artifact("03_summary.md")
    summary = summary_path.read_text("utf-8") if summary_path.exists() else ctx.summary
    if not summary.strip():
        raise AppError("API_ERROR", "总结内容为空")
    content = _document_header(meta) + summary.strip() + "\n"

    document = repo.find_document(str(meta["platform"]), str(meta["video_id"]))
    if document is None:
        doc_id = repo.create_document(
            platform=str(meta["platform"]),
            video_id=str(meta["video_id"]),
            title=str(meta.get("title") or ""),
            author=str(meta.get("author") or ""),
            cover_url=str(meta.get("cover_url") or ""),
            duration=int(meta.get("duration") or 0),
            source_url=str(meta.get("source_url") or ""),
            content_type=str(meta.get("content_type") or "其他"),
            summary_depth=str(ctx.options.get("depth") or "standard"),
            template_id=str(ctx.options.get("template_id") or ""),
            file_path="",
        )
        document = repo.get_document(doc_id)
    assert document is not None
    doc_id = document["id"]
    path = config.documents_dir() / f"{doc_id}.md"

    if path.exists():
        repo.add_version(doc_id, path.read_text("utf-8"), reason="regenerate")

    _write_text(path, content)
    stat = path.stat()
    repo.update_document(
        doc_id,
        title=str(meta.get("title") or document["title"]),
        author=str(meta.get("author") or ""),
        cover_url=str(meta.get("cover_url") or ""),
        duration=int(meta.get("duration") or 0),
        source_url=str(meta.get("source_url") or ""),
        content_type=str(meta.get("content_type") or "其他"),
        summary_depth=str(ctx.options.get("depth") or "standard"),
        template_id=str(ctx.options.get("template_id") or ""),
        file_path=str(path),
        file_mtime=stat.st_mtime,
        status="ready",
    )
    if not repo.tags_of(doc_id):
        model = repo.current_model()
        if model is not None:
            try:
                tags, usage = await extract_tags(model, summary)
                if tags:
                    repo.set_document_tags(doc_id, tags)
                repo.add_usage(
                    kind="tags",
                    model_id=model["id"],
                    document_id=doc_id,
                    task_id=ctx.task["id"],
                    prompt_tokens=usage["prompt_tokens"],
                    completion_tokens=usage["completion_tokens"],
                )
            except Exception:  # 标签是增强信息，失败不影响正文
                pass
    repo.index_document(doc_id, str(meta.get("title") or ""), content, repo.tags_of(doc_id))
    repo.update_task(ctx.task["id"], document_id=doc_id)
    ctx.document_id = doc_id
    bus.publish({"type": "document", "document_id": doc_id, "action": "generated"})


STAGES = {
    StageName.LINK: run_link_parse,
    StageName.SUBTITLE: run_subtitle,
    StageName.AI: run_ai_analyze,
    StageName.RENDER: run_render_md,
}
