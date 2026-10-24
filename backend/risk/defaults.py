from backend.risk.features import FEATURES

DEFAULT_SETTINGS = {
    "weights":              {},
    "highThreshold":        70,
    "mediumThreshold":      40,
    "horizonDays":          30,
    "expiringWindowDays":   7,
    "prolongWaitGraceDays": 5,
    "countWithdrawBalance": False,
    "referenceTime":        None, # последняя дата в данных
}

def default_settings():
    s = dict(DEFAULT_SETTINGS)
    s["weights"] = { uid: f.baseWeight for uid, f in FEATURES.items() }
    return s

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
        if not 0 <= w <= 1:
            raise ValueError(f"weight {uid} must be 0..1")
    if not 0 <= s["mediumThreshold"] <= s["highThreshold"] <= 100:
        raise ValueError("bad thresholds")
    if s["horizonDays"] < 1 or s["expiringWindowDays"] < 1 or s["prolongWaitGraceDays"] < 0:
        raise ValueError("bad days")
    return s
