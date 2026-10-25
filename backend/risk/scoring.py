from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from backend.models import *
from backend.risk.actions import Action, recommend
from backend.risk.defaults import merge_settings
from backend.risk.features import FEATURES, Context, Funding

LEVELS = ("high", "medium", "low", "no_data")

@dataclass
class Reason:
    feature: str
    title: str
    serviceId: int
    strength: float
    weight: float
    impact: float # weight * strength
    text: str
    kind: str = "risk" # protective - snizhaet risk

@dataclass
class ServiceRisk:
    serviceId: int
    name: str
    status: ServiceStatus
    paymentTerm: PaymentTerm
    price: int
    expiresAt: datetime
    autoProlong: bool
    risk: float
    revenue: int        # vyruchka v gorizonte s uchetom platezhesposobnosti klienta
    revenueFull: int    # ta zhe vyruchka bez ogranicheniya
    expectedLoss: int
    nextChargeAt: datetime
    reasons: list = field(default_factory=list)

@dataclass
class CustomerRisk:
    accountId: int
    email: str
    balance: int
    totalReplenished: int
    availableFunds: int
    capacity: int    
    score: float
    level: str
    loyalty: float
    expectedLoss: int
    revenue: int
    revenueFull: int
    action: Action | None = None
    reasons: list = field(default_factory=list)
    services: list = field(default_factory=list)

@dataclass
class FeatureImpact:
    feature: str
    title: str
    weight: float
    customers: int    
    services: int
    expectedLoss: int 
    kind: str = "risk"

@dataclass
class Summary:
    referenceTime: datetime
    horizonDays: int
    customersTotal: int
    customersByLevel: dict
    expectedLossTotal: int
    expectedLossByLevel: dict
    revenueTotal: int
    revenueFullTotal: int
    servicesAtRisk: int
    revenueByTerm: dict = field(default_factory=dict)
    expectedLossByTerm: dict = field(default_factory=dict)
    features: list = field(default_factory=list)

@dataclass
class ChartPoint:
    date: str
    deleted: int                
    deletedObserved: int       
    expectedNonrenewals: float 
    servicesAtRisk: int       

@dataclass
class ChurnChart:
    bucket: str         # day | week
    referenceDate: str
    horizonDays: int
    points: list = field(default_factory=list)


def get_now( snapshot, settings ):
    ref = settings["referenceTime"]
    if ref == "now":
        return datetime.now(timezone.utc)
    if ref:
        moment = parsetime(ref)
        return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)
    return snapshot.latest_event() or datetime.now(timezone.utc)

def get_level( score, settings ):
    if score is None:
        return "no_data"
    if score >= settings["highThreshold"]:
        return "high"
    if score >= settings["mediumThreshold"]:
        return "medium"
    return "low"

def get_funds( account, settings ):
    funds = account.balance
    if account.bonusState == BonusState.UNLOCKED:
        funds += account.bonusBalance
    if settings["countWithdrawBalance"]:
        funds += account.withdrawBalance
    return funds

def plan_funding( services, funds, now, horizonDays ):
    until = now + timedelta(days=horizonDays)
    charges = []
    for s in services:
        moment = max(s.expiresAt, now) 
        while moment < until:
            charges.append(( moment, s.id, s.price ))
            moment = next_period(moment, s.paymentTerm)
    charges.sort()

    plan = {}
    for moment, sid, price in charges:
        f = plan.setdefault(sid, Funding())
        f.due += price
        paid = min(funds, price)
        funds -= paid
        if paid < price:
            f.shortfall += price - paid
            if not f.firstUnpaidAt:
                f.firstUnpaidAt = moment
    return plan

def payment_capacity( account, services, funds, now, horizonDays ):
    started = min((s.createdAt for s in services), default=None)
    tenure = max((now - started).total_seconds() / 86400, 1) if started else 1
    return funds + round(account.totalReplenished / tenure * horizonDays)


def score_service( service, ctx ):
    reasons = []
    survive = 1.0 # П(1 - w*f) po riskovym priznakam
    protect = 1.0 # П(1 - w*f) po zashchitnym: umen'shaet itogovyi risk
    for uid, f in FEATURES.items():
        w = ctx.settings["weights"].get(uid, f.baseWeight)
        if w <= 0:
            continue
        signal = f.fn(service, ctx)
        if not signal or signal.strength <= 0:
            continue
        impact = w * signal.strength
        if f.kind == "protective":
            protect *= 1 - impact
        else:
            survive *= 1 - impact
        reasons.append(Reason(uid, f.name, service.id, round(signal.strength, 3), w, round(impact, 3), signal.reason, f.kind))

    base = 1 - survive
    if base <= 0:
        # snizhat' nechego: zashchitnye prichiny u zdorovogo klienta tol'ko putayut
        reasons = [r for r in reasons if r.kind != "protective"]
        protect = 1.0
    risk = base * protect # (1 - П(1 - w*f)) * П(1 - w*p)
    revenue = round(service.price * ctx.settings["horizonDays"] / TERM_DAYS[service.paymentTerm])
    reasons.sort(key=lambda r: r.impact, reverse=True)
    return ServiceRisk(service.id, service.name, service.status, service.paymentTerm, service.price,
                       service.expiresAt, service.autoProlong, round(risk, 4), revenue, revenue,
                       round(risk * revenue), max(service.expiresAt, ctx.now), reasons)


def score_customer( account, services, txByService, now, settings ):
    live = [s for s in services if s.is_live]
    funds = get_funds(account, settings)
    horizon = settings["horizonDays"]
    ctx = Context(account, services, txByService, now, settings, funds,
                  plan_funding(live, funds, now, horizon))

    scored = [score_service(s, ctx) for s in live]
    capacity = payment_capacity(account, services, funds, now, horizon)
    full = sum(s.revenueFull for s in scored)
    if settings["capRevenueByCapacity"] and full > capacity:
        # bol'she, chem klient sposoben zaplatit', my by i tak ne poluchili
        for s in scored:
            s.revenue = round(s.revenueFull * capacity / full)
            s.expectedLoss = round(s.risk * s.revenue)
    scored.sort(key=lambda s: s.risk, reverse=True)
    score = round(100 * scored[0].risk, 1) if scored else None

    # priznaki urovnya akkaunta srabatyvayut na kazhdoi usluge, ostavlyaem odin raz
    reasons = []
    for r in sorted([r for s in scored for r in s.reasons], key=lambda r: r.impact, reverse=True):
        if not any(x.feature == r.feature and x.text == r.text for x in reasons):
            reasons.append(r)
    shortfall = sum(f.shortfall for f in ctx.funding.values())

    return CustomerRisk(
        accountId=account.id,
        email=account.email,
        balance=account.balance,
        totalReplenished=account.totalReplenished,
        availableFunds=funds,
        capacity=capacity,
        score=score,
        level=get_level(score, settings),
        loyalty=None if score is None else round(100 - score, 1),
        expectedLoss=sum(s.expectedLoss for s in scored),
        revenue=sum(s.revenue for s in scored),
        revenueFull=full,
        action=recommend(reasons, account, shortfall),
        reasons=reasons,
        services=scored,
    )


def evaluate( snapshot, settings=None ):
    settings = merge_settings(base=settings)
    now = get_now(snapshot, settings)

    servicesByOwner = defaultdict(list)
    for s in snapshot.services:
        servicesByOwner[s.ownerId].append(s)
    txByService = defaultdict(list)
    for t in snapshot.transactions:
        txByService[t.serviceId].append(t)

    customers = [score_customer(a, servicesByOwner[a.id], txByService, now, settings) for a in snapshot.accounts]
    customers.sort(key=lambda c: ( c.score is None, -(c.score or 0), -c.expectedLoss, c.accountId ))
    return customers


def summarize( customers, snapshot, settings=None ):
    settings = merge_settings(base=settings)
    byLevel = { l: 0 for l in LEVELS }
    lossByLevel = { l: 0 for l in LEVELS }
    for c in customers:
        byLevel[c.level] += 1
        lossByLevel[c.level] += c.expectedLoss

    atRisk = 0
    byTerm = { t.value: 0 for t in PaymentTerm }
    lossByTerm = { t.value: 0 for t in PaymentTerm }
    impact = { uid: FeatureImpact(uid, f.name, settings["weights"].get(uid, f.baseWeight), 0, 0, 0, f.kind)
               for uid, f in FEATURES.items() }
    for c in customers:
        hit = set()
        for s in c.services:
            if s.risk * 100 >= settings["mediumThreshold"]:
                atRisk += 1
            byTerm[s.paymentTerm.value] += s.revenue
            lossByTerm[s.paymentTerm.value] += s.expectedLoss

            total = sum(r.impact for r in s.reasons if r.kind != "protective")
            for r in s.reasons:
                fi = impact[r.feature]
                fi.services += 1
                hit.add(r.feature)
                if total and r.kind != "protective":
                    fi.expectedLoss += round(s.expectedLoss * r.impact / total)
        for uid in hit:
            impact[uid].customers += 1

    return Summary(
        referenceTime=get_now(snapshot, settings),
        horizonDays=settings["horizonDays"],
        customersTotal=len(customers),
        customersByLevel=byLevel,
        expectedLossTotal=sum(c.expectedLoss for c in customers),
        expectedLossByLevel=lossByLevel,
        revenueTotal=sum(c.revenue for c in customers),
        revenueFullTotal=sum(c.revenueFull for c in customers),
        servicesAtRisk=atRisk,
        revenueByTerm=byTerm,
        expectedLossByTerm=lossByTerm,
        features=sorted(impact.values(), key=lambda f: ( -f.expectedLoss, -f.customers )),
    )


def timeline( customers, snapshot, settings=None, observed=None ):
    settings = merge_settings(base=settings)
    observed = observed or {}
    now = get_now(snapshot, settings)
    horizon = settings["horizonDays"]
    grace = timedelta(days=settings["prolongWaitGraceDays"])
    today = now.date()
    end = today + timedelta(days=horizon)

    deleted, seen = defaultdict(int), defaultdict(int)
    for s in snapshot.services:
        if s.status != ServiceStatus.DELETED:
            continue
        at = observed.get(s.id)
        if at is not None:
            day = min(at, now).date()
            seen[day] += 1
        else:
            day = min(s.expiresAt, now).date()
        deleted[day] += 1

    expected, atRisk = defaultdict(float), defaultdict(int)
    for c in customers:
        for s in c.services:
            event = s.expiresAt + grace if s.status == ServiceStatus.PROLONG_WAIT else s.expiresAt
            day = max(event, now).date()
            if day > end:
                continue
            expected[day] += s.risk
            if s.risk * 100 >= settings["mediumThreshold"]:
                atRisk[day] += 1

    start = min([today - timedelta(days=horizon), *deleted])
    bucket = "day" if (end - start).days <= 120 else "week"
    step = timedelta(days=7 if bucket == "week" else 1)
    key = (lambda d: d - timedelta(days=d.weekday())) if bucket == "week" else (lambda d: d)

    points = {}
    cur = key(start)
    while cur <= end:
        points[cur] = ChartPoint(cur.isoformat(), 0, 0, 0.0, 0)
        cur += step
    for day, n in deleted.items():
        points[key(day)].deleted += n
    for day, n in seen.items():
        points[key(day)].deletedObserved += n
    for day, risk in expected.items():
        points[key(day)].expectedNonrenewals += risk
    for day, n in atRisk.items():
        points[key(day)].servicesAtRisk += n
    for p in points.values():
        p.expectedNonrenewals = round(p.expectedNonrenewals, 2)
    return ChurnChart(bucket, today.isoformat(), horizon, list(points.values()))
