from backend.models import parsetime
from backend.risk.features import FEATURES

DEFAULT_SETTINGS = {
    "weights":              {},
    "highThreshold":        70,
    "mediumThreshold":      40,
    "horizonDays":          30,
    "expiringWindowDays":   7,
    "prolongWaitGraceDays": 5,
    "paymentLookbackDays":  90,  
    "countWithdrawBalance": False,
    "capRevenueByCapacity": True, 
    "bigSpenderThreshold":  100_000, 
    "newCustomerDays":      30,    
    "loyalTenureDays":      180,   
    "referenceTime":        None,  # последняя дата
}

NUMBERS = ("highThreshold", "mediumThreshold", "horizonDays", "expiringWindowDays", "prolongWaitGraceDays", "paymentLookbackDays",
           "bigSpenderThreshold", "newCustomerDays", "loyalTenureDays")
FLAGS = ("countWithdrawBalance", "capRevenueByCapacity")

def default_settings():
    s = dict(DEFAULT_SETTINGS)
    s["weights"] = { uid: f.baseWeight for uid, f in FEATURES.items() }
    return s

def check_reference( value ):
    if value is None or value == "now":
        return
    if not isinstance(value, str):
        raise ValueError("referenceTime must be null, 'now' or an ISO datetime")
    try:
        parsetime(value)
    except ValueError:
        raise ValueError(f"referenceTime: cannot parse {value!r}, expected ISO datetime like 2026-10-19T15:00:00Z") from None

def is_number( v ):
    return isinstance(v, (int, float)) and not isinstance(v, bool)

def merge_settings( patch=None, base=None ):
    s = default_settings()
    for src in ( base or {}, patch or {} ):
        for k, v in src.items():
            if k not in s:
                raise ValueError(f"unknown setting: {k}")
            if k == "weights":
                s["weights"] = { **s["weights"], **v }
            else:
                s[k] = v

    for uid, w in s["weights"].items():
        if uid not in FEATURES:
            raise ValueError(f"unknown feature: {uid}")
        if not is_number(w) or not 0 <= w <= 1:
            raise ValueError(f"weight {uid} must be 0..1")
    for k in NUMBERS:
        if not is_number(s[k]):
            raise ValueError(f"{k} must be a number")
    for k in FLAGS:
        if not isinstance(s[k], bool):
            raise ValueError(f"{k} must be true/false")
    if not 0 <= s["mediumThreshold"] <= s["highThreshold"] <= 100:
        raise ValueError("bad thresholds")
    if s["horizonDays"] < 1 or s["expiringWindowDays"] < 1 or s["prolongWaitGraceDays"] < 0 or s["paymentLookbackDays"] < 1 \
            or s["newCustomerDays"] < 1 or s["loyalTenureDays"] < 1:
        raise ValueError("bad days")
    if s["bigSpenderThreshold"] < 0:
        raise ValueError("bigSpenderThreshold must be >= 0")
    check_reference(s["referenceTime"])
    return s
