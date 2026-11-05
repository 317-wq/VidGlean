"""OpenAI 兼容客户端封装：并发限制、错误归一、用量提取。"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from vidglean.core.errors import AppError
from vidglean.security import secrets as secret_store

_DEFAULT_CONCURRENCY = 2
_semaphore: asyncio.Semaphore | None = None
_semaphore_size = _DEFAULT_CONCURRENCY


def set_concurrency(value: int) -> None:
    global _semaphore, _semaphore_size
    value = max(1, int(value))
    if value == _semaphore_size and _semaphore is not None:
        return
    _semaphore_size = value
    _semaphore = asyncio.Semaphore(value)


def semaphore() -> asyncio.Semaphore:
    if _semaphore is None:
        set_concurrency(_DEFAULT_CONCURRENCY)
    assert _semaphore is not None
    return _semaphore


def api_key_of(model: dict[str, Any]) -> str:
    key = secret_store.get_secret(f"model:{model['id']}") or ""
    if not key:
        raise AppError("API_KEY_INVALID", "该模型没有配置 API Key")
    return key


def build(model: dict[str, Any]):
    from openai import AsyncOpenAI

    return AsyncOpenAI(
        api_key=api_key_of(model),
        base_url=model.get("base_url") or None,
        timeout=float(model.get("timeout") or 120),
        max_retries=1,
    )


def translate(exc: Exception) -> AppError:
    if isinstance(exc, AppError):
        return exc
    try:
        import openai
    except Exception:  # pragma: no cover
        return AppError("UNKNOWN", detail=str(exc))

    if isinstance(exc, openai.AuthenticationError):
        return AppError("API_KEY_INVALID", detail=str(exc))
    if isinstance(exc, openai.PermissionDeniedError):
        return AppError("API_KEY_INVALID", detail=str(exc))
    if isinstance(exc, openai.RateLimitError):
        return AppError("RATE_LIMIT", detail=str(exc))
    if isinstance(exc, openai.APITimeoutError):
        return AppError("TIMEOUT", detail=str(exc))
    if isinstance(exc, openai.APIConnectionError):
        return AppError("NETWORK", detail=str(exc))
    if isinstance(exc, openai.NotFoundError):
        return AppError("MODEL_NOT_FOUND", detail=str(exc))
    if isinstance(exc, openai.BadRequestError):
        text = str(exc).lower()
        if "quota" in text or "balance" in text or "insufficient" in text:
            return AppError("INSUFFICIENT_QUOTA", detail=str(exc))
        return AppError("API_ERROR", detail=str(exc))
    if isinstance(exc, openai.InternalServerError):
        return AppError("SERVER_ERROR", detail=str(exc))
    return AppError("API_ERROR", detail=f"{type(exc).__name__}: {exc}")


def _usage_of(response: Any) -> dict[str, int]:
    usage = getattr(response, "usage", None)
    if usage is None:
        return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    return {
        "prompt_tokens": int(getattr(usage, "prompt_tokens", 0) or 0),
        "completion_tokens": int(getattr(usage, "completion_tokens", 0) or 0),
        "total_tokens": int(getattr(usage, "total_tokens", 0) or 0),
    }


async def complete(
    model: dict[str, Any],
    messages: list[dict[str, str]],
    *,
    temperature: float | None = None,
    max_tokens: int | None = None,
    allow_reasoning_fallback: bool = True,
) -> tuple[str, dict[str, int]]:
    client = build(model)
    try:
        async with semaphore():
            response = await client.chat.completions.create(
                model=model["model"],
                messages=messages,
                temperature=model.get("temperature", 0.5) if temperature is None else temperature,
                max_tokens=max_tokens or int(model.get("max_tokens") or 4096),
            )
    except Exception as exc:
        raise translate(exc) from exc
    choice = response.choices[0]
    content = (choice.message.content or "").strip()
    if not content and allow_reasoning_fallback:
        content = (getattr(choice.message, "reasoning_content", "") or "").strip()
    return content, _usage_of(response)


async def stream(
    model: dict[str, Any],
    messages: list[dict[str, str]],
    *,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> AsyncIterator[tuple[str, dict[str, int] | None]]:
    """流式返回 (delta, usage)。usage 只在最后一条出现。"""
    client = build(model)
    try:
        async with semaphore():
            response = await client.chat.completions.create(
                model=model["model"],
                messages=messages,
                temperature=model.get("temperature", 0.5) if temperature is None else temperature,
                max_tokens=max_tokens or int(model.get("max_tokens") or 4096),
                stream=True,
                stream_options={"include_usage": True},
            )
            async for chunk in response:
                if getattr(chunk, "usage", None):
                    yield "", _usage_of(chunk)
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                text = getattr(delta, "content", None)
                if text:
                    yield text, None
    except Exception as exc:
        raise translate(exc) from exc
