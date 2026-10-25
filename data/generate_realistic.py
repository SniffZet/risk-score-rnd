import argparse, calendar, json, random
from datetime import datetime, timedelta, timezone

REF = datetime(2026, 10, 19, 15, 0, tzinfo=timezone.utc)
TERMS = ["hour", "week", "month", "quarter_year", "half_year", "year"]
TERM_W = [0.10, 0.10, 0.55, 0.12, 0.08, 0.05]
TERM_DAYS = {"hour": 1 / 24, "week": 7, "month": 30.44, "quarter_year": 91.3, "half_year": 182.6, "year": 365.25}
PRICE = {"hour": (1, 8), "week": (200, 1000), "month": (500, 6000), "quarter_year": (1500, 15000),
         "half_year": (3000, 30000), "year": (5000, 60000)}
STATUSES = ["active", "suspended", "prolong_wait", "deleted", "blocked"]
STATUS_W = [0.80, 0.05, 0.04, 0.08, 0.03]

def iso(d):
    return d.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")

def add_term(value, term):
    if term == "hour":
        return value + timedelta(hours=1)
    if term == "week":
        return value + timedelta(weeks=1)
    months = {"month": 1, "quarter_year": 3, "half_year": 6, "year": 12}[term]
    idx = value.year * 12 + value.month - 1 + months
    y, m = divmod(idx, 12)
    return value.replace(year=y, month=m + 1, day=min(value.day, calendar.monthrange(y, m + 1)[1]))

def generate(n_accounts, seed):
    rng = random.Random(seed)
    accounts, services, transactions = [], [], []
    sid = tid = 0
    for aid in range(1, n_accounts + 1):
        balance = min(int(rng.lognormvariate(8.3, 1.3)), 300_000)
        paid_total = 0
        n_services = rng.choices([1, 2, 3, 4, 5], [35, 30, 20, 10, 5])[0]
        for _ in range(n_services):
            sid += 1
            term = rng.choices(TERMS, TERM_W)[0]
            price = rng.randint(*PRICE[term])
            status = rng.choices(STATUSES, STATUS_W)[0]
            td = TERM_DAYS[term]
            created = REF - timedelta(days=rng.uniform(1, 720))
            if status in ("active", "suspended"):
                expires = REF + timedelta(days=rng.uniform(0, td))
            elif status == "prolong_wait":
                expires = REF - timedelta(days=rng.uniform(0, 5))
            elif status == "deleted":
                expires = REF - timedelta(days=rng.uniform(10, 400))
            else:
                expires = REF + timedelta(days=rng.uniform(-30, 60))
            if expires < created + timedelta(days=td):
                created = expires - timedelta(days=td * rng.uniform(1, 4))
            auto = rng.random() < 0.7
            services.append({"id": sid, "name": f"srv-{sid:04d}", "ownerId": aid, "paymentTerm": term, "autoProlong": auto,
                             "createdAt": iso(created), "expiresAt": iso(expires), "status": status, "price": price})
            tid += 1
            transactions.append({"id": tid, "amount": price, "status": "performed", "performedAt": iso(created + timedelta(minutes=1)),
                                 "createdAt": iso(created), "type": "order", "serviceId": sid})
            paid_total += price
            periods = min(int((min(expires, REF) - created).total_seconds() / 86400 / td), 12)
            moment = created
            for k in range(periods):
                moment = add_term(moment, term)
                if moment > REF:
                    break
                tid += 1
                failed = (status == "prolong_wait" and k == periods - 1) or rng.random() < 0.06
                transactions.append({"id": tid, "amount": price, "status": "not_performed" if failed else "performed",
                                     "performedAt": None if failed else iso(moment + timedelta(minutes=2)),
                                     "createdAt": iso(moment), "type": "prolong", "serviceId": sid})
                if not failed:
                    paid_total += price
        accounts.append({"id": aid, "email": f"client-{aid:04d}@example.test", "balance": balance,
                         "withdrawBalance": rng.randint(0, balance // 10) if rng.random() < 0.2 else 0,
                         "totalReplenished": balance + paid_total + rng.randint(0, 20_000),
                         "bonusBalance": rng.randint(0, 3000), "bonusState": rng.choice(["locked", "unlocked"])})
    return {"accounts": accounts, "services": services, "transactions": transactions}

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--accounts", type=int, default=300)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    json.dump(generate(a.accounts, a.seed), open(a.out, "w"), ensure_ascii=False)
    print("written", a.out)
