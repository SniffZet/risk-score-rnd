"""Pydantic-схемы: контракт API для фронтенда.

Имена полей намеренно совпадают с моделью риска (``CustomRisk``,
``ServiceRisk``, ``Summary`` из ``backend.risk.scoring``): так ML-человеку
знаком ответ, а фронт получает те же названия, что и в его моках —
``score``, ``level``, ``expectedLoss``, ``loyalty``.

Правила:
* никаких «сырых» dict в ответах;
* мутабельные значения по умолчанию только через ``Field(default_factory=...)``;
* входные схемы не смешиваются с выходными.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

RiskLevel = Literal["high", "medium", "low", "no_data"]
SortField = Literal[
    "accountId",
    "email",
    "balance",
    "totalReplenished",
    "score",
    "expectedLoss",
    "revenue",
    "loyalty",
]
SortOrder = Literal["asc", "desc"]


# ---------------------------------------------------------------------------
# Авторизация
# ---------------------------------------------------------------------------
class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=256)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    username: str


# ---------------------------------------------------------------------------
# Причины риска и услуги
# ---------------------------------------------------------------------------
class ReasonOut(BaseModel):
    """Совпадает с ``risk.scoring.Reason``."""

    feature: str = Field(examples=["prolong_wait"])
    title: str = Field(examples=["Ожидает оплаты"])
    serviceId: int
    strength: float = Field(description="сила сигнала признака, 0..1")
    weight: float = Field(description="вес признака, 0..1")
    impact: float = Field(description="weight × strength")
    text: str


class ServiceRiskOut(BaseModel):
    """Совпадает с ``risk.scoring.ServiceRisk``."""

    serviceId: int
    name: str
    status: str
    paymentTerm: str
    price: int = Field(description="цена в еврокопейках")
    expiresAt: datetime
    autoProlong: bool
    risk: float = Field(description="риск услуги, 0..1")
    revenue: int = Field(description="выручка в горизонте, еврокопейки")
    expectedLoss: int = Field(description="ожидаемые потери, еврокопейки")
    reasons: list[ReasonOut] = Field(default_factory=list)


class CustomerListItem(BaseModel):
    """Строка списка клиентов."""

    accountId: int
    email: str
    balance: int = Field(description="баланс в еврокопейках")
    totalReplenished: int = Field(description="всего пополнений, еврокопейки")
    availableFunds: int = Field(description="доступные средства, еврокопейки")
    score: float | None = Field(default=None, description="0..100, null если нет живых услуг")
    level: RiskLevel = "no_data"
    loyalty: float | None = Field(default=None, description="100 − score")
    expectedLoss: int = 0
    revenue: int = 0


class CustomerDetail(CustomerListItem):
    """Карточка клиента: добавляются причины и разбивка по услугам."""

    reasons: list[ReasonOut] = Field(default_factory=list)
    services: list[ServiceRiskOut] = Field(default_factory=list)


class CustomersPage(BaseModel):
    items: list[CustomerListItem]
    total: int
    limit: int
    offset: int


# ---------------------------------------------------------------------------
# Аналитика
# ---------------------------------------------------------------------------
class SummaryOut(BaseModel):
    """Совпадает с ``risk.scoring.Summary``."""

    referenceTime: datetime
    horizonDays: int
    customersTotal: int
    customersByLevel: dict[str, int]
    expectedLossTotal: int
    expectedLossByLevel: dict[str, int]
    revenueTotal: int
    servicesAtRisk: int


class ChurnChartPoint(BaseModel):
    date: str
    deleted_actual: int
    expected_nonrenewals: int


# ---------------------------------------------------------------------------
# Настройки модели
# ---------------------------------------------------------------------------
class FeatureMeta(BaseModel):
    """Признак для построения формы настроек на фронте.

    Границы веса (0..1) заданы здесь, чтобы фронт не хардкодил их.
    """

    code: str
    title: str
    description: str
    default_weight: float
    min_weight: float = 0.0
    max_weight: float = 1.0


class SettingsOut(BaseModel):
    weights: dict[str, float]
    highThreshold: float
    mediumThreshold: float
    horizonDays: int
    expiringWindowDays: int
    prolongWaitGraceDays: int
    countWithdrawBalance: bool
    referenceTime: datetime | str | None = None
    features: list[FeatureMeta] = Field(default_factory=list)


class SettingsPatch(BaseModel):
    """Частичное обновление: приходит только то, что реально меняют."""

    model_config = ConfigDict(extra="forbid")

    weights: dict[str, float] | None = None
    highThreshold: float | None = None
    mediumThreshold: float | None = None
    horizonDays: int | None = None
    expiringWindowDays: int | None = None
    prolongWaitGraceDays: int | None = None
    countWithdrawBalance: bool | None = None
    referenceTime: str | None = None


# ---------------------------------------------------------------------------
# Загрузка снапшота
# ---------------------------------------------------------------------------
class SnapshotIn(BaseModel):
    """Тело PUT /source/snapshot.

    Разделы объявлены списками словарей намеренно: формат ``data.json`` —
    внешний, и строгая проверка выполняется в ``services.normalize``, которая
    повторяет ограничения SQL-схемы и даёт понятные ошибки с номерами записей.
    """

    accounts: list[dict] = Field(default_factory=list)
    services: list[dict] = Field(default_factory=list)
    transactions: list[dict] = Field(default_factory=list)


class SnapshotOut(BaseModel):
    status: str = "ok"
    counts: dict[str, int]
    summary: SummaryOut | None = None
