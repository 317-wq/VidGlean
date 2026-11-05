"""图片代理：B 站封面有防盗链，直接给浏览器会被 403，这里带 Referer 取回来。"""

from __future__ import annotations

import hashlib
from pathlib import Path
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Query
from fastapi.responses import Response

from vidglean import config
from vidglean.core.errors import AppError

router = APIRouter(prefix="/api")

ALLOWED_HOSTS = ("hdslb.com", "bilibili.com", "biliimg.com")
_HEADERS = {
    "Referer": "https://www.bilibili.com/",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
}


def _cache_path(url: str) -> Path:
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()
    return config.tmp_dir() / "covers" / digest


@router.get("/image")
async def proxy_image(url: str = Query(...)) -> Response:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in ("http", "https") or not any(
        host == allowed or host.endswith("." + allowed) for allowed in ALLOWED_HOSTS
    ):
        raise AppError("CONFLICT", "不支持的图片地址")

    cache = _cache_path(url)
    if cache.exists():
        return Response(
            cache.read_bytes(),
            media_type="image/jpeg",
            headers={"Cache-Control": "public, max-age=86400"},
        )

    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            response = await client.get(url, headers=_HEADERS)
    except httpx.HTTPError as exc:
        raise AppError("NETWORK", "封面加载失败", detail=str(exc)) from exc
    if response.status_code != 200 or not response.content:
        raise AppError("NETWORK", f"封面加载失败（HTTP {response.status_code}）")

    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_bytes(response.content)
    media_type = response.headers.get("content-type", "image/jpeg").split(";")[0]
    return Response(
        response.content,
        media_type=media_type,
        headers={"Cache-Control": "public, max-age=86400"},
    )
