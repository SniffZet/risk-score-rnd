from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

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

from backend.risk.actions import Action, recommend
from backend.risk.defaults import (
    DEFAULT_SETTINGS,
    default_settings,
    merge_settings,
)
from backend.risk.features import FEATURES, Context, Feature, Funding, Signal

from backend.risk.scoring import (
    LEVELS,
    ChartPoint,
    ChurnChart,
    CustomerRisk,
    FeatureImpact,
    Reason,
    ServiceRisk,
    Summary,
    evaluate,
    get_level,
    get_now,
    payment_capacity,
    summarize,
    timeline,
)

RISK_LEVELS = LEVELS

__all__ = [
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
    "Action",
    "Context",
    "DEFAULT_SETTINGS",
    "FEATURES",
    "Feature",
    "Funding",
    "Signal",
    "default_settings",
    "merge_settings",
    "recommend",
    "ChartPoint",
    "ChurnChart",
    "CustomerRisk",
    "FeatureImpact",
    "LEVELS",
    "Reason",
    "RISK_LEVELS",
    "ServiceRisk",
    "Summary",
    "evaluate",
    "get_level",
    "get_now",
    "payment_capacity",
    "summarize",
    "timeline",
    "as_utc",
    "utcnow",
    "Session",
    "Transition",
    "User",
]


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


@dataclass(slots=True)
class Transition:
    at: datetime
    serviceId: int
    ownerId: int
    serviceName: str
    field: str
    old: str | None
    new: str


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
