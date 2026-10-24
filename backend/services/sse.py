"""Server-Sent Events: рассылка событий подключённым клиентам.

Очередь ограничена по размеру: медленный подписчик не должен съедать память
процесса. При переполнении самое старое событие отбрасывается — для UI это
корректно, потому что важен факт «данные обновились», а не вся их история.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator

from backend.config import settings

_subscribers: set[asyncio.Queue] = set()


def subscriber_count() -> int:
    return len(_subscribers)


async def publish(event: str, data: dict | None = None) -> None:
    """Разослать событие всем подписчикам, не блокируясь на медленных."""
    payload = {"event": event, "data": data or {}}
    for queue in list(_subscribers):
        if queue.full():
            try:
                queue.get_nowait()  # выбрасываем самое старое
            except asyncio.QueueEmpty:  # pragma: no cover - гонка
                pass
        try:
            queue.put_nowait(payload)
        except asyncio.QueueFull:  # pragma: no cover - защита
            pass


@asynccontextmanager
async def subscription() -> AsyncIterator[asyncio.Queue]:
    """Подписка на события на время работы HTTP-соединения.

    Отдаём именно очередь, а не async-генератор: потребитель вызывает
    ``queue.get()`` под таймаутом для heartbeat, и таймаут отменяет только
    этот ``get()``, а не саму подписку. Если бы подписка была генератором,
    отмена ``__anext__`` закрыла бы её целиком.
    """
    queue: asyncio.Queue = asyncio.Queue(maxsize=settings.SSE_QUEUE_SIZE)
    _subscribers.add(queue)
    try:
        yield queue
    finally:
        _subscribers.discard(queue)


def reset() -> None:
    """Сбросить всех подписчиков (остановка приложения, тесты)."""
    _subscribers.clear()
