"""进程内事件总线，用于 SSE 推送。"""

from __future__ import annotations

import asyncio
import contextlib
from typing import Any


class EventBus:
    def __init__(self, queue_size: int = 200) -> None:
        self._queue_size = queue_size
        self._subscribers: set[asyncio.Queue[dict[str, Any]]] = set()

    def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=self._queue_size)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
        self._subscribers.discard(queue)

    def publish(self, event: dict[str, Any]) -> None:
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                # 慢消费者直接丢弃，前端重连后会重新拉全量列表。
                with contextlib.suppress(Exception):
                    queue.get_nowait()

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)


bus = EventBus()
