from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator

from backend.config import settings

_subscribers: set[asyncio.Queue] = set()


def subscriber_count() -> int:
    return len(_subscribers)


async def publish(event: str, data: dict | None = None) -> None:
    payload = {"event": event, "data": data or {}}
    for queue in list(_subscribers):
        if queue.full():
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:  # pragma: no cover
                pass
        try:
            queue.put_nowait(payload)
        except asyncio.QueueFull:  # pragma: no cover
            pass


@asynccontextmanager
async def subscription() -> AsyncIterator[asyncio.Queue]:
    queue: asyncio.Queue = asyncio.Queue(maxsize=settings.SSE_QUEUE_SIZE)
    _subscribers.add(queue)
    try:
        yield queue
    finally:
        _subscribers.discard(queue)


def reset() -> None:
    _subscribers.clear()
