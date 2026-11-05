"""SSE 事件流：任务进度与文档变更。"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from vidglean.core.events import bus

router = APIRouter(prefix="/api")


@router.get("/events")
async def events(request: Request) -> StreamingResponse:
    queue = bus.subscribe()

    async def generator():
        try:
            yield ": connected\n\n"
            while True:
                if await request.is_disconnected():
                    return
                try:
                    event: dict[str, Any] = await asyncio.wait_for(queue.get(), timeout=15)
                except TimeoutError:
                    yield ": ping\n\n"
                    continue
                payload = json.dumps(event, ensure_ascii=False)
                yield f"event: {event.get('type', 'message')}\ndata: {payload}\n\n"
        finally:
            bus.unsubscribe(queue)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
