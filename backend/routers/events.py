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
    async def event_generator():
        async with sse.subscription() as queue:
            yield {"event": "ready", "data": "{}"}
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
