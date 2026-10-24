"""Состояние приложения: последний результат пересчёта.

Результаты скоринга дополнительно сохраняются в хранилище (см.
``Repository.save_risk``). Этот объект — быстрый кэш для сводки и служебных
эндпоинтов, а не единственный источник правды.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from backend.domain import Summary


@dataclass
class AppState:
    summary: Summary | None = None
    last_updated: datetime | None = None
    last_error: str | None = None
    recompute_count: int = 0
    realtime_enabled: bool = True


state = AppState()
