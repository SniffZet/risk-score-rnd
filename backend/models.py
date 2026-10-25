from dataclasses import dataclass

import calendar
from enum import StrEnum
from datetime import datetime, timedelta

class BonusState( StrEnum ):
    LOCKED      = "locked"
    UNLOCKED    = "unlocked"

@dataclass
class AccountDetails:
    id: int
    email: str
    balance: int
    withdrawBalance: int
    totalReplenished: int
    bonusBalance: int
    bonusState: BonusState
    @classmethod
    def format_dict(self, data: dict):
        return self(
            id=int(data["id"]),
            email=data["email"],
            balance=int(data["balance"]),
            withdrawBalance=int(data["withdrawBalance"]),
            totalReplenished=int(data["totalReplenished"]),
            bonusBalance=int(data["bonusBalance"]),
            bonusState=BonusState(data["bonusState"]),
        )

class ServiceStatus(StrEnum):
    ACTIVE          = "active"
    SUSPENDED       = "suspended"
    PROLONG_WAIT    = "prolong_wait"
    DELETED         = "deleted"
    BLOCKED         = "blocked"

class PaymentTerm(StrEnum):
    HOUR            = "hour"
    WEEK            = "week"
    MONTH           = "month"
    QUARTER_YEAR    = "quarter_year"
    HALF_YEAR       = "half_year"
    YEAR            = "year"

@dataclass
class ServiceDetails:
    id: int
    name: str
    ownerId: int
    paymentTerm: PaymentTerm
    autoProlong: bool
    createdAt: datetime
    expiresAt: datetime
    status: ServiceStatus
    price: int

    @property
    def is_live(self) -> bool:
        return (self.status in ( ServiceStatus.ACTIVE, ServiceStatus.SUSPENDED, ServiceStatus.PROLONG_WAIT ))

    @classmethod
    def format_dict( self, data: dict ):
        return self(
            id=int(data["id"]),
            name=data["name"],
            ownerId=int(data["ownerId"]),
            paymentTerm=PaymentTerm(data["paymentTerm"]),
            autoProlong=bool(data["autoProlong"]),
            createdAt=parsetime(data["createdAt"]),
            expiresAt=parsetime(data["expiresAt"]),
            status=ServiceStatus(data["status"]),
            price=int(data["price"]),
        )

class TransactionStatus(StrEnum):
    PERFORMED       = "performed"
    NOT_PERFORMED   = "not_performed"

class TransactionType(StrEnum):
    PROLONG         = "prolong"
    ORDER           = "order"

@dataclass
class TransactionDetails:
    id: int
    amount: int
    status: TransactionStatus
    performedAt: datetime | None
    createdAt: datetime
    type: TransactionType
    serviceId: int

    @property
    def is_performed(self) -> bool:
        return self.status == TransactionStatus.PERFORMED

    @classmethod
    def format_dict( self, data: dict ):
        return self(
            id=int(data["id"]),
            amount=int(data["amount"]),
            status=TransactionStatus(data["status"]),
            performedAt=parsetime(data.get("performedAt")),
            createdAt=parsetime(data["createdAt"]),
            type=TransactionType(data["type"]),
            serviceId=int(data["serviceId"]),
        )

@dataclass
class Snapshot:
    accounts: list[AccountDetails]
    services: list[ServiceDetails]
    transactions: list[TransactionDetails]

    @classmethod
    def format_dict( self, data: dict ):
        return self(
            accounts=[AccountDetails.format_dict(x) for x in data.get("accounts", [])],
            services=[ServiceDetails.format_dict(x) for x in data.get("services", [])],
            transactions=[TransactionDetails.format_dict(x) for x in data.get("transactions", [])],
        )

    def latest_event(self) -> datetime | None:
        moments = [s.createdAt for s in self.services]
        moments += [t.performedAt or t.createdAt for t in self.transactions]
        return max(moments, default=None)


TERM_DAYS = {
    PaymentTerm.HOUR:           1 / 24,
    PaymentTerm.WEEK:           7,
    PaymentTerm.MONTH:          365.25 / 12,
    PaymentTerm.QUARTER_YEAR:   365.25 / 4,
    PaymentTerm.HALF_YEAR:      365.25 / 2,
    PaymentTerm.YEAR:           365.25,
}

TERM_MONTHS = {
    PaymentTerm.MONTH:          1,
    PaymentTerm.QUARTER_YEAR:   3,
    PaymentTerm.HALF_YEAR:      6,
    PaymentTerm.YEAR:           12,
}

def next_period( moment: datetime, term: PaymentTerm ) -> datetime:
    if term == PaymentTerm.HOUR:
        return moment + timedelta(hours=1)
    if term == PaymentTerm.WEEK:
        return moment + timedelta(weeks=1)
    total = moment.month - 1 + TERM_MONTHS[term]
    year, month = moment.year + total // 12, total % 12 + 1
    day = min(moment.day, calendar.monthrange(year, month)[1])
    return moment.replace(year=year, month=month, day=day)

def parsetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
