from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from backend.domain import ChurnChart, Summary


@dataclass
class AppState:
    summary: Summary | None = None
    chart: ChurnChart | None = None
    fingerprint: str | None = None
    last_updated: datetime | None = None
    last_error: str | None = None
    recompute_count: int = 0
    realtime_enabled: bool = True


state = AppState()
