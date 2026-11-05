"""Bilibili 解析：链接识别、元信息、字幕。"""

from __future__ import annotations

import re
from typing import Any

import httpx

from vidglean.core.errors import AppError
from vidglean.core.models import ContentType, VideoMeta
from vidglean.security import secrets as secret_store

SESSION_KEY = "bilibili:sessdata"
BVID_RE = re.compile(r"(BV[0-9A-Za-z]{10})")
_SHORT_HOSTS = ("b23.tv", "bili2233.cn")

_initialized = False

_TYPE_RULES: list[tuple[tuple[str, ...], str]] = [
    (("教程", "教学", "入门", "实战", "课程", "手把手", "从零", "源码", "编码"), ContentType.TECH),
    (("科普", "原理", "为什么", "解密", "揭秘", "知识", "解读"), ContentType.SCIENCE),
    (("经验", "分享", "复盘", "心得", "避坑", "踩坑"), ContentType.EXPERIENCE),
    (("观点", "评论", "锐评", "辩论", "访谈", "对话"), ContentType.OPINION),
    (("技巧", "生活", "美食", "健身", "装修", "收纳"), ContentType.LIFE),
    (("搞笑", "整活", "游戏", "娱乐", "vlog", "日常"), ContentType.FUN),
]


def _init() -> None:
    global _initialized
    if _initialized:
        return
    _initialized = True
    try:
        from bilibili_api import request_settings

        request_settings.set("impersonate", "chrome131")
    except Exception:  # pragma: no cover - 取决于 curl_cffi 版本
        pass


def _credential():
    from bilibili_api import Credential

    sessdata = secret_store.get_secret(SESSION_KEY)
    if not sessdata:
        return Credential(), False
    return Credential(sessdata=sessdata), True


def is_supported(url: str) -> bool:
    lowered = url.lower()
    return "bilibili.com" in lowered or "b23.tv" in lowered or bool(BVID_RE.search(url))


async def extract_video_id(url: str) -> str:
    _init()
    match = BVID_RE.search(url)
    if match:
        return match.group(1)
    if any(host in url for host in _SHORT_HOSTS):
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
                response = await client.get(url.strip())
        except httpx.TimeoutException as exc:
            raise AppError("TIMEOUT", detail=str(exc)) from exc
        except httpx.HTTPError as exc:
            raise AppError("NETWORK", detail=str(exc)) from exc
        match = BVID_RE.search(str(response.url))
        if match:
            return match.group(1)
    raise AppError("INVALID_URL", "无法从链接中识别 BV 号")


def _translate(exc: Exception) -> AppError:
    code = getattr(exc, "code", None)
    text = str(exc)
    if code in (-404, 62002, 62004):
        return AppError("VIDEO_NOT_FOUND", detail=text)
    if code in (-403, 62012):
        return AppError("VIDEO_PRIVATE", detail=text)
    if code in (-352, -412, 412):
        return AppError("RATE_LIMIT", detail=text)
    lowered = text.lower()
    if "timeout" in lowered or "timed out" in lowered:
        return AppError("TIMEOUT", detail=text)
    if "conn" in lowered or "network" in lowered:
        return AppError("NETWORK", detail=text)
    return AppError("UNKNOWN", detail=f"{type(exc).__name__}: {text}")


def infer_content_type(title: str, tname: str = "") -> str:
    haystack = f"{tname} {title}".lower()
    for keywords, content_type in _TYPE_RULES:
        if any(keyword.lower() in haystack for keyword in keywords):
            return content_type
    if tname:
        if "科技" in tname:
            return ContentType.TECH
        if "知识" in tname:
            return ContentType.SCIENCE
        if "生活" in tname or "美食" in tname:
            return ContentType.LIFE
        if "游戏" in tname or "影视" in tname:
            return ContentType.FUN
    return ContentType.OTHER


async def fetch_meta(video_id: str) -> VideoMeta:
    _init()
    from bilibili_api import video

    credential, _ = _credential()
    client = video.Video(bvid=video_id, credential=credential)
    try:
        info: dict[str, Any] = await client.get_info()
    except Exception as exc:
        raise _translate(exc) from exc
    tname = str(info.get("tname") or "")
    title = str(info.get("title") or "")
    return VideoMeta(
        platform="bilibili",
        video_id=video_id,
        title=title,
        author=str((info.get("owner") or {}).get("name") or ""),
        cover_url=str(info.get("pic") or ""),
        duration=int(info.get("duration") or 0),
        source_url=f"https://www.bilibili.com/video/{video_id}",
        content_type=infer_content_type(title, tname),
        description=str(info.get("desc") or "")[:2000],
        extra={
            "cid": info.get("cid"),
            "tname": tname,
            "pubdate": info.get("pubdate"),
            "pages": len(info.get("pages") or []),
        },
    )


async def fetch_subtitle(video_id: str, cid: int | None = None) -> dict[str, Any]:
    """返回 {lang, lan_doc, text, segments}。"""
    _init()
    from bilibili_api import video

    credential, has_credential = _credential()
    client = video.Video(bvid=video_id, credential=credential)
    if cid is None:
        try:
            info = await client.get_info()
        except Exception as exc:
            raise _translate(exc) from exc
        cid = int(info.get("cid") or 0)
    try:
        payload = await client.get_subtitle(cid)
    except Exception as exc:
        raise _translate(exc) from exc

    subtitles = payload.get("subtitles") or []
    if not subtitles:
        if not has_credential:
            raise AppError("AUTH_REQUIRED", "获取字幕需要登录凭证，请先在设置中配置 B 站 SESSDATA")
        raise AppError("NO_SUBTITLE")

    chosen = next((item for item in subtitles if "zh" in str(item.get("lan", ""))), subtitles[0])
    url = str(chosen.get("subtitle_url") or "")
    if url.startswith("//"):
        url = "https:" + url
    if not url:
        raise AppError("NO_SUBTITLE")

    try:
        async with httpx.AsyncClient(timeout=30) as http:
            response = await http.get(url)
            response.raise_for_status()
            data = response.json()
    except httpx.TimeoutException as exc:
        raise AppError("TIMEOUT", detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise AppError("NETWORK", detail=str(exc)) from exc
    except ValueError as exc:
        raise AppError("NETWORK", "字幕内容不是合法 JSON", detail=str(exc)) from exc

    segments = [
        {
            "from": item.get("from"),
            "to": item.get("to"),
            "content": str(item.get("content") or "").strip(),
        }
        for item in data.get("body") or []
        if str(item.get("content") or "").strip()
    ]
    text = "，".join(segment["content"] for segment in segments)
    if not text.strip():
        raise AppError("NO_SUBTITLE")
    return {
        "lang": str(chosen.get("lan") or ""),
        "lan_doc": str(chosen.get("lan_doc") or ""),
        "text": text,
        "segments": segments,
    }
