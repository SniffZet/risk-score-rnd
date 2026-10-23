from dataclasses import dataclass

from backend.models import *

@dataclass
class Signal:
    strength: float # TotalWeight=Strength*BaseWeight(of risk factor)
    reason: str

@dataclass
class Context:
    account: AccountDetails
    services: list[ServiceDetails]


# dekorator, ne trogat' ub'yu!!!
FEATURES = {}

@dataclass(frozen=True)
class Feature:
    uid: str
    name: str
    baseWeight: float
    fn: object

def feature( uid: str, name: str, weight: float ):
    def register( fn ):
        assert uid not in FEATURES, f'feature uid must be unique! [{uid}]x2'
        FEATURES[uid] = Feature( uid, name, weight, fn )
    return register