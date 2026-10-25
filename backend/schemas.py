from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.domain import AccountDetails, PaymentTerm, ServiceStatus

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


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=256)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    username: str


class ProvidersOut(BaseModel):
    password: bool = True
    oidc: bool = False
    oidcName: str | None = None
    oidcLoginUrl: str | None = None


class ReasonOut(BaseModel):
    feature: str = Field(examples=["prolong_wait"])
    title: str = Field(examples=["Ожидает оплаты"])
    serviceId: int
    strength: float = Field(description="сила сигнала признака, 0..1")
    weight: float = Field(description="вес признака, 0..1")
    impact: float = Field(description="weight × strength")
    text: str
    kind: Literal["risk", "protective"] = Field(default="risk", description="protective — признак снижает риск")


class ActionOut(BaseModel):
    code: str = Field(examples=["remind_payment"])
    title: str = Field(examples=["Напомнить об оплате"])
    text: str


class ServiceRiskOut(BaseModel):
    serviceId: int
    name: str
    status: ServiceStatus
    paymentTerm: PaymentTerm
    price: int = Field(description="цена в еврокопейках")
    expiresAt: datetime
    autoProlong: bool
    risk: float = Field(description="риск услуги, 0..1")
    revenue: int = Field(description="выручка в горизонте с учётом платёжеспособности, еврокопейки")
    revenueFull: int = Field(description="выручка в горизонте без ограничения, еврокопейки")
    expectedLoss: int = Field(description="ожидаемые потери, еврокопейки")
    nextChargeAt: datetime = Field(description="ближайшее списание или оплата")
    reasons: list[ReasonOut] = Field(default_factory=list)


class TransitionOut(BaseModel):
    at: datetime
    serviceId: int
    ownerId: int
    serviceName: str
    field: Literal["status", "autoProlong"]
    old: str | None = None
    new: str


class CustomerListItem(BaseModel):
    accountId: int
    email: str
    balance: int = Field(description="баланс в еврокопейках")
    totalReplenished: int = Field(description="всего пополнений, еврокопейки")
    availableFunds: int = Field(description="доступные средства, еврокопейки")
    capacity: int = Field(description="платёжеспособность за горизонт, еврокопейки")
    score: float | None = Field(default=None, description="0..100, null если нет живых услуг")
    level: RiskLevel = "no_data"
    loyalty: float | None = Field(default=None, description="100 − score")
    expectedLoss: int = 0
    revenue: int = 0
    revenueFull: int = 0
    action: ActionOut | None = Field(default=None, description="рекомендованное действие")
    reasons: list[ReasonOut] = Field(
        default_factory=list,
        description="главные причины оценки по убыванию вклада (в списке — до 3, в карточке — все)",
    )


class CustomerDetail(CustomerListItem):
    account: AccountDetails | None = Field(
        default=None, description="запись аккаунта в формате models.AccountDetails"
    )
    reasons: list[ReasonOut] = Field(default_factory=list)
    services: list[ServiceRiskOut] = Field(default_factory=list)
    history: list[TransitionOut] = Field(
        default_factory=list, description="изменения услуг клиента, которые наблюдал анализатор"
    )


class CustomersPage(BaseModel):
    items: list[CustomerListItem]
    total: int
    limit: int
    offset: int


class FeatureImpactOut(BaseModel):
    feature: str
    title: str
    weight: float
    customers: int = Field(description="у скольких клиентов сработал")
    services: int = Field(description="на скольких услугах сработал")
    expectedLoss: int = Field(description="доля ожидаемых потерь, отнесённая к признаку, еврокопейки; у защитных 0")
    kind: Literal["risk", "protective"] = "risk"


class SummaryOut(BaseModel):
    referenceTime: datetime
    horizonDays: int
    customersTotal: int
    customersByLevel: dict[str, int]
    expectedLossTotal: int
    expectedLossByLevel: dict[str, int]
    revenueTotal: int = Field(description="выручка в горизонте с учётом платёжеспособности")
    revenueFullTotal: int = Field(description="выручка в горизонте без ограничения")
    servicesAtRisk: int
    revenueByTerm: dict[str, int] = Field(default_factory=dict)
    expectedLossByTerm: dict[str, int] = Field(default_factory=dict)
    features: list[FeatureImpactOut] = Field(default_factory=list)


class ChurnChartPoint(BaseModel):
    date: str = Field(description="начало интервала, YYYY-MM-DD")
    deleted: int = Field(description="факт: удалённые услуги")
    deletedObserved: int = Field(description="из них переход в deleted наблюдался анализатором")
    expectedNonrenewals: float = Field(description="прогноз: ожидаемое число непродлений")
    servicesAtRisk: int = Field(description="прогноз: услуги с риском не ниже среднего порога")


class ChurnChartOut(BaseModel):
    bucket: Literal["day", "week"]
    referenceDate: str
    horizonDays: int
    points: list[ChurnChartPoint] = Field(default_factory=list)


class FeatureMeta(BaseModel):
    code: str
    title: str
    description: str
    default_weight: float
    min_weight: float = 0.0
    max_weight: float = 1.0
    kind: Literal["risk", "protective"] = Field(default="risk", description="protective — снижает риск, а не повышает")


class SettingsOut(BaseModel):
    weights: dict[str, float]
    highThreshold: float
    mediumThreshold: float
    horizonDays: int
    expiringWindowDays: int
    prolongWaitGraceDays: int
    paymentLookbackDays: int
    countWithdrawBalance: bool
    capRevenueByCapacity: bool
    bigSpenderThreshold: int = Field(description="пополнений за всё время, еврокопейки, с которых клиент крупный")
    newCustomerDays: int
    loyalTenureDays: int
    referenceTime: datetime | str | None = None
    features: list[FeatureMeta] = Field(default_factory=list)


class SettingsPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    weights: dict[str, float] | None = None
    highThreshold: float | None = None
    mediumThreshold: float | None = None
    horizonDays: int | None = None
    expiringWindowDays: int | None = None
    prolongWaitGraceDays: int | None = None
    paymentLookbackDays: int | None = None
    countWithdrawBalance: bool | None = None
    capRevenueByCapacity: bool | None = None
    bigSpenderThreshold: int | None = None
    newCustomerDays: int | None = None
    loyalTenureDays: int | None = None
    referenceTime: str | None = None


class SettingsPreviewOut(BaseModel):
    settings: SettingsOut
    summary: SummaryOut


class SnapshotIn(BaseModel):
    accounts: list[dict] = Field(default_factory=list)
    services: list[dict] = Field(default_factory=list)
    transactions: list[dict] = Field(default_factory=list)


class SnapshotPatchIn(BaseModel):
    accounts: list[dict] = Field(default_factory=list)
    services: list[dict] = Field(default_factory=list)
    transactions: list[dict] = Field(default_factory=list)


class SnapshotOut(BaseModel):
    status: str = "ok"
    counts: dict[str, int] = Field(description="записей в данных после загрузки")
    applied: dict[str, int] = Field(default_factory=dict, description="записей пришло в запросе")
    transitions: int = Field(default=0, description="изменений услуг записано в журнал")
    summary: SummaryOut | None = None
