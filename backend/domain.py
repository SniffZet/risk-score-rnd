"""Единая точка контракта приложения.

Здесь мы НЕ описываем свои модели риска. Источник правды — код человека,
который делает модель: пакет ``app/risk`` (models / features / scoring /
defaults). Этот модуль только реэкспортирует его типы и добавляет
прикладные утилиты, которых в модели нет.

Зачем так:
* остальной бэкенд импортирует типы из одного места (``backend.domain``),
  а не из шести модулей модели;
* если ML-человек изменит свои структуры, правится ровно один файл;
* случайно «поправить» его логику в другом месте невозможно.

ВАЖНО: ``app/risk`` вендорится как есть. Логику модели здесь не дублируют
и не переписывают — её меняет только её автор.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

# --- типы данных организаторов (models.py) ---------------------------------
from backend.models import (
    TERM_DAYS,
    TERM_MONTHS,
    AccountDetails,
    BonusState,
    PaymentTerm,
    ServiceDetails,
    ServiceStatus,
    Snapshot,
    TransactionDetails,
    TransactionStatus,
    TransactionType,
    next_period,
    parsetime,
)

# --- настройки и признаки ---------------------------------------------------
from backend.risk.defaults import (
    DEFAULT_SETTINGS,
    default_settings,
    merge_settings,
)
from backend.risk.features import FEATURES, Context, Feature, Funding, Signal

# --- результаты скоринга ----------------------------------------------------
from backend.risk.scoring import (
    LEVELS,
    CustomerRisk,
    Reason,
    ServiceRisk,
    Summary,
    evaluate,
    get_level,
    get_now,
    summarize,
)

#: Уровни риска в порядке от самого опасного.
RISK_LEVELS = LEVELS

__all__ = [
    # models
    "AccountDetails",
    "BonusState",
    "PaymentTerm",
    "ServiceDetails",
    "ServiceStatus",
    "Snapshot",
    "TERM_DAYS",
    "TERM_MONTHS",
    "TransactionDetails",
    "TransactionStatus",
    "TransactionType",
    "next_period",
    "parsetime",
    # defaults / features
    "Context",
    "DEFAULT_SETTINGS",
    "FEATURES",
    "Feature",
    "Funding",
    "Signal",
    "default_settings",
    "merge_settings",
    # scoring
    "CustomerRisk",
    "LEVELS",
    "Reason",
    "RISK_LEVELS",
    "ServiceRisk",
    "Summary",
    "evaluate",
    "get_level",
    "get_now",
    "summarize",
    # утилиты приложения
    "as_utc",
    "utcnow",
    # авторизация (наша часть, к модели отношения не имеет)
    "Session",
    "User",
]


# ---------------------------------------------------------------------------
# Авторизация: наши типы, модель их не знает
# ---------------------------------------------------------------------------
@dataclass(slots=True)
class User:
    id: int
    username: str
    password_hash: str


@dataclass(slots=True)
class Session:
    id: str
    user_id: int
    created_at: datetime
    expires_at: datetime

    def is_expired(self, now: datetime | None = None) -> bool:
        return self.expires_at <= as_utc(now or utcnow())


# ---------------------------------------------------------------------------
# Прикладные утилиты (в модели их нет — они нужны только API-слою)
# ---------------------------------------------------------------------------
def utcnow() -> datetime:
    """Текущее время, всегда timezone-aware (UTC).

    Используется для служебных вещей: срок жизни сессии, метки времени.
    Сама модель берёт «сейчас» из данных (``Snapshot.latest_event``), потому
    что тестовый набор заморожен на конкретной дате.
    """
    return datetime.now(timezone.utc)


def as_utc(value: datetime) -> datetime:
    """Привести дату к aware-UTC.

    Нужно, потому что модель сравнивает даты между собой (``latest_event``,
    ``days_left``), и смесь «наивных» и aware-значений падает с TypeError.
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
