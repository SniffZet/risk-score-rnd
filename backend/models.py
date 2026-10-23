from dataclasses import dataclass

import json
from enum import StrEnum
from datetime import datetime

class BonusState( StrEnum ):
    LOCKED      = "locked"
    UNLOCKED    = "unlocked"

@dataclass
class AccountDetails:
    id: int
    email: str
    balance: int
    withdrawBalance: int
    totalReplenished: int # total topup
    bonusBalance: int
    bonusState: BonusState
    @classmethod
    def format_dict(self, data: dict):
        return self(
            id=int(data["id"]),
            email=data["email"],
            balance=int(data["balance"]),
            withdrawBalance=int(data["withdrawBalance"]),
            totalRepleinshed=int(data["totalReplenished"]),
            bonusBalance=int(data["bonusBalance"]),
            BonusState=BonusState(data["bonusState"]),
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

def parsetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))

@dataclass
class ServiceDetails:
    id: int
    name: str
    ownerId: int
    paymentTerm: str
    autoProlong: bool
    createdAt: datetime
    expiresAt: datetime
    status: str
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