import json
from enum import StrEnum

class BonusState( StrEnum ):
    LOCKED      = "locked"
    UNLOCKED    = "unlocked"


class AccountDetails:
    id: int
    email: str
    balance: int
    withdrawBalance: int
    totalReplenished: int # total topup
    bonusBalance: int
    bonusState: BonusState

    def __init__(self, data: dict):
        return self(
            id=int(data["id"]),
            email=data["email"],
            balance=int(data["balance"]),
            withdrawBalance=int(data["withdrawBalance"]),
            totalRepleinshed=int(data["totalReplenished"]),
            bonusBalance=int(data["bonusBalance"]),
            BonusState=BonusState(data["bonusState"]),
        )
        

