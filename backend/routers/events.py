"""SSE-поток событий для фронтенда."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

from backend.config import settings
from backend.deps import CurrentUser
from backend.services import sse

router = APIRouter()


@router.get("/events", summary="Поток событий (SSE)")
async def events(request: Request, _: CurrentUser) -> EventSourceResponse:
    """Отдаёт события ``recalculated``.

    Отправляем heartbeat (``ping``), чтобы прокси и браузер не закрывали
    «тихое» соединение.
    """

    async def event_generator():
        async with sse.subscription() as queue:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    message = await asyncio.wait_for(
                        queue.get(), timeout=settings.SSE_HEARTBEAT_SEC
                    )
                except asyncio.TimeoutError:
                    yield {"event": "ping", "data": "{}"}
                    continue
                yield {"event": message["event"], "data": message["data"]}

    return EventSourceResponse(event_generator())
