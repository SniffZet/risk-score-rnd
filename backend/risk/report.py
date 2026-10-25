# python -m backend.risk.report data/data.json 15 prolong_wait=0.5

import json
import sys

from backend.models import Snapshot
from backend.risk.features import eur
from backend.risk.scoring import evaluate, summarize

sys.stdout.reconfigure(encoding="utf-8")

path = sys.argv[1] if len(sys.argv) > 1 else "data/data.json"
top = int(sys.argv[2]) if len(sys.argv) > 2 else 10
weights = { k: float(v) for k, v in (a.split("=") for a in sys.argv[3:]) }

with open(path, encoding="utf-8") as f:
    snapshot = Snapshot.format_dict(json.load(f))

settings = { "weights": weights }
customers = evaluate(snapshot, settings)
summary = summarize(customers, snapshot, settings)

print(f"now {summary.referenceTime:%Y-%m-%d %H:%M}, horizon {summary.horizonDays}d")
print(f"levels {summary.customersByLevel}")
print(f"loss {eur(summary.expectedLossTotal)} / revenue {eur(summary.revenueTotal)}, services at risk {summary.servicesAtRisk}")
print()

for c in customers[:top]:
    print(f"#{c.accountId} {c.email} score={c.score} {c.level} funds={eur(c.availableFunds)} loss={eur(c.expectedLoss)}")
    for r in c.reasons[:3]:
        print(f"    +{r.impact:.2f} {r.text}")
