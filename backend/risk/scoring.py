from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from backend.models import *
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
    revenue: int
    expectedLoss: int
    reasons: list = field(default_factory=list)

@dataclass
class CustomerRisk:
    accountId: int
    email: str
    balance: int
    totalReplenished: int
    availableFunds: int
    score: float # None esli net zhivyh uslug
    level: str
    loyalty: float
    expectedLoss: int
    revenue: int
    reasons: list = field(default_factory=list)
    services: list = field(default_factory=list)

@dataclass
class Summary:
    referenceTime: datetime
    horizonDays: int
    customersTotal: int
    customersByLevel: dict
    expectedLossTotal: int
    expectedLossByLevel: dict
    revenueTotal: int
    servicesAtRisk: int


def get_now( snapshot, settings ):
    ref = settings["referenceTime"]
    if ref == "now":
        return datetime.now(timezone.utc)
    if ref:
        return parsetime(ref)
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

# spisyvaem vse prodleniya akkaunta po poryadku s balansa, smotrim gde ne hvatit
def plan_funding( services, funds, now, horizonDays ):
    until = now + timedelta(days=horizonDays)
    charges = []
    for s in services:
        moment = max(s.expiresAt, now) # prolong_wait - platit' nado uzhe seichas
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


def score_service( service, ctx ):
    reasons = []
    survive = 1.0
    for uid, f in FEATURES.items():
        w = ctx.settings["weights"].get(uid, f.baseWeight)
        if w <= 0:
            continue
        signal = f.fn(service, ctx)
        if not signal or signal.strength <= 0:
            continue
        impact = w * signal.strength
        survive *= 1 - impact
        reasons.append(Reason(uid, f.name, service.id, round(signal.strength, 3), w, round(impact, 3), signal.reason))

    risk = 1 - survive # 1 - П(1 - w*f)
    revenue = round(service.price * ctx.settings["horizonDays"] / TERM_DAYS[service.paymentTerm])
    reasons.sort(key=lambda r: r.impact, reverse=True)
    return ServiceRisk(service.id, service.name, service.status, service.paymentTerm, service.price,
                       service.expiresAt, service.autoProlong, round(risk, 4), revenue, round(risk * revenue), reasons)


def score_customer( account, services, txByService, now, settings ):
    live = [s for s in services if s.is_live]
    funds = get_funds(account, settings)
    ctx = Context(account, services, txByService, now, settings, funds,
                  plan_funding(live, funds, now, settings["horizonDays"]))

    scored = [score_service(s, ctx) for s in live]
    scored.sort(key=lambda s: s.risk, reverse=True)
    score = round(100 * scored[0].risk, 1) if scored else None

    # churn_history srabatyvaet na kazhdoi usluge, ostavlyaem odin raz
    reasons = []
    for r in sorted([r for s in scored for r in s.reasons], key=lambda r: r.impact, reverse=True):
        if not any(x.feature == r.feature and x.text == r.text for x in reasons):
            reasons.append(r)

    return CustomerRisk(
        accountId=account.id,
        email=account.email,
        balance=account.balance,
        totalReplenished=account.totalReplenished,
        availableFunds=funds,
        score=score,
        level=get_level(score, settings),
        loyalty=None if score is None else round(100 - score, 1),
        expectedLoss=sum(s.expectedLoss for s in scored),
        revenue=sum(s.revenue for s in scored),
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
    # snachala samye opasnye, no_data v konce
    customers.sort(key=lambda c: ( c.score is None, -(c.score or 0), c.accountId ))
    return customers


def summarize( customers, snapshot, settings=None ):
    settings = merge_settings(base=settings)
    byLevel = { l: 0 for l in LEVELS }
    lossByLevel = { l: 0 for l in LEVELS }
    for c in customers:
        byLevel[c.level] += 1
        lossByLevel[c.level] += c.expectedLoss

    atRisk = 0
    for c in customers:
        for s in c.services:
            if s.risk * 100 >= settings["mediumThreshold"]:
                atRisk += 1

    return Summary(
        referenceTime=get_now(snapshot, settings),
        horizonDays=settings["horizonDays"],
        customersTotal=len(customers),
        customersByLevel=byLevel,
        expectedLossTotal=sum(c.expectedLoss for c in customers),
        expectedLossByLevel=lossByLevel,
        revenueTotal=sum(c.revenue for c in customers),
        servicesAtRisk=atRisk,
    )
