"""视频字幕 -> Markdown 总结。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from vidglean.ai import client as ai_client
from vidglean.ai import prompts
from vidglean.core.errors import AppError
from vidglean.core.utils import estimate_tokens
from vidglean.markdown_render import strip_code_fence

# 单次请求的字幕上限（字符），超过先做分段提炼
CHUNK_CHARS = 9000


@dataclass
class SummaryResult:
    text: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    chunks: int = 1


def split_text(text: str, size: int = CHUNK_CHARS) -> list[str]:
    text = text.strip()
    if len(text) <= size:
        return [text]
    parts: list[str] = []
    start = 0
    length = len(text)
    while start < length:
        end = min(start + size, length)
        if end < length:
            window = text[max(start, end - 300) : end]
            cut = max(window.rfind(ch) for ch in "。！？\n")
            if cut > 0:
                end = max(start, end - 300) + cut + 1
        chunk = text[start:end].strip()
        if chunk:
            parts.append(chunk)
        start = end
    return parts


async def summarize(
    *,
    meta: dict[str, Any],
    transcript: str,
    template_text: str,
    depth: str,
    extra: str,
    model: dict[str, Any],
) -> SummaryResult:
    content_type = str(meta.get("content_type") or "其他")
    system = prompts.system_prompt(depth, content_type)
    prompt_tokens = 0
    completion_tokens = 0

    chunks = split_text(transcript)
    if len(chunks) > 1 and estimate_tokens(transcript) > 4000:
        notes: list[str] = []
        for index, chunk in enumerate(chunks, start=1):
            text, usage = await ai_client.complete(
                model,
                [
                    {"role": "system", "content": "你是视频字幕提炼助手，只输出要点列表。"},
                    {"role": "user", "content": prompts.chunk_prompt(chunk, index, len(chunks))},
                ],
                temperature=0.3,
            )
            if text:
                notes.append(f"### 第 {index} 段要点\n{text}")
            prompt_tokens += usage["prompt_tokens"]
            completion_tokens += usage["completion_tokens"]
        user = prompts.reduce_prompt(
            meta=meta, template_text=template_text, notes="\n\n".join(notes), extra=extra
        )
    else:
        user = prompts.summary_user_prompt(
            meta=meta, template_text=template_text, transcript=transcript, extra=extra
        )

    text, usage = await ai_client.complete(
        model,
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
    )
    prompt_tokens += usage["prompt_tokens"]
    completion_tokens += usage["completion_tokens"]
    text = strip_code_fence(text)
    if not text:
        raise AppError("API_ERROR", "模型返回了空内容")
    return SummaryResult(
        text=text,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        chunks=len(chunks),
    )


_TAG_SPLIT = re.compile(r"[,，、;；\n/|]+")
_TERM_HEADING = re.compile(r"^#{2,3}\s*(关键名词|核心概念|关键概念|术语|关键词)", re.M)
_TAG_BAD_CHARS = set("。！？：；…（）()【】“”\"'`")
_TAG_BAD_PREFIX = (
    "首先",
    "然后",
    "因此",
    "所以",
    "可以",
    "应该",
    "需要",
    "注意",
    "文档",
    "内容",
    "标签",
    "例如",
    "如下",
    "每个",
    "用逗号",
    "提取",
)


def _clean_tags(text: str, limit: int) -> list[str]:
    """只接受短名词，挡掉模型把推理过程当标签输出的情况。"""
    tags: list[str] = []
    for raw in _TAG_SPLIT.split(text):
        tag = raw.strip().strip("#-*`·・ ").strip()
        if not (2 <= len(tag) <= 10):
            continue
        if any(ch in tag for ch in _TAG_BAD_CHARS):
            continue
        if tag.startswith(_TAG_BAD_PREFIX):
            continue
        if tag not in tags:
            tags.append(tag)
    return tags[:limit]


def _fallback_terms(content: str, limit: int) -> list[str]:
    """模型没给出标签时，从「关键名词」小节里取条目。"""
    match = _TERM_HEADING.search(content)
    if not match:
        return []
    section = content[match.end() :]
    next_heading = re.search(r"^#{1,3}\s", section, re.M)
    if next_heading:
        section = section[: next_heading.start()]
    tags: list[str] = []
    for line in section.splitlines():
        line = line.strip()
        if not line.startswith(("-", "*", "1", "2", "3", "4", "5")):
            continue
        item = re.sub(r"^[-\*\d.、\s]+", "", line)
        item = item.split("：")[0].split(":")[0].strip(" `*")
        if 2 <= len(item) <= 12 and item not in tags:
            tags.append(item)
    return tags[:limit]


async def extract_tags(
    model: dict[str, Any], content: str, limit: int = 6
) -> tuple[list[str], dict[str, int]]:
    """从总结正文里提取标签；失败或结果不可用时退回模板小节解析。"""
    usage: dict[str, int] = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    try:
        text, usage = await ai_client.complete(
            model,
            [
                {
                    "role": "system",
                    "content": "从给定文档中提取 3 到 6 个标签，只用逗号分隔的名词，"
                    "不要句子、不要解释。每个标签不超过 10 个字。",
                },
                {"role": "user", "content": content[:4000]},
            ],
            temperature=0.2,
            max_tokens=160,
            allow_reasoning_fallback=False,
        )
    except Exception:
        return _fallback_terms(content, limit), usage
    tags = _clean_tags(text, limit)
    if not tags:
        tags = _fallback_terms(content, limit)
    return tags, usage

