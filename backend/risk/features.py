from dataclasses import dataclass, field
from datetime import datetime, timedelta

from backend.models import *

@dataclass
class Signal:
    strength: float # TotalWeight=Strength*BaseWeight(of risk factor)
    reason: str

@dataclass
class Funding:
    due: int = 0
    shortfall: int = 0
    firstUnpaidAt: datetime = None

@dataclass
class Context:
    account: AccountDetails
    services: list[ServiceDetails]
    transactions: dict # serviceId -> [TransactionDetails]
    now: datetime
    settings: dict
    availableFunds: int = 0
    funding: dict = field(default_factory=dict) # serviceId -> Funding

    def days_left( self, service ):
        return (service.expiresAt - self.now).total_seconds() / 86400


# dekorator, ne trogat' ub'yu!!!
FEATURES = {}

@dataclass(frozen=True)
class Feature:
    uid: str
    name: str
    baseWeight: float
    fn: object
    description: str = ""
    kind: str = "risk"

def feature( uid: str, name: str, weight: float, description: str = "", kind: str = "risk" ):
    assert kind in ( "risk", "protective" ), f'feature kind must be risk or protective [{uid}]'
    def register( fn ):
        assert uid not in FEATURES, f'feature uid must be unique! [{uid}]x2'
        FEATURES[uid] = Feature( uid, name, weight, fn, description, kind )
        return fn
    return register

######

def eur( cents ):
    return f"€{cents / 100:.2f}"

def days( d ):
    d = abs(d)
    if d < 1:
        return f"{d * 24:.0f} ч"
    return f"{d:.0f} дн."

def expiry( left ):
    if left < 0:
        return f"срок истёк {days(left)} назад"
    return f"истекает через {days(left)}"


@feature("prolong_wait", "Ожидает оплаты", 0.9, "Период истёк, услугу удалят через несколько дней")
def prolong_wait( service, ctx ):
    if service.status != ServiceStatus.PROLONG_WAIT:
        return None
    grace = ctx.settings["prolongWaitGraceDays"]
    left = grace + ctx.days_left(service)
    if left <= 0 or grace <= 0:
        overdue = f" {days(left)} назад" if left < 0 else ""
        return Signal(1.0, f"{service.name}: срок ожидания оплаты истёк{overdue}, по правилам статусов услуга уже должна быть удалена")
    return Signal(0.6 + 0.4 * (1 - left / grace), f"{service.name}: ждёт оплаты, до удаления {days(left)}")


def expiring_window( service, ctx ):
    if service.paymentTerm == PaymentTerm.HOUR:
        return None
    return min(ctx.settings["expiringWindowDays"], TERM_DAYS[service.paymentTerm] / 2)

def is_expiring( service, ctx ):
    if service.autoProlong or service.status not in ( ServiceStatus.ACTIVE, ServiceStatus.SUSPENDED ):
        return False
    window = expiring_window(service, ctx)
    return window is not None and ctx.days_left(service) <= window


MIN_URGENCY = 0.25

@feature("insufficient_funds", "Не хватает средств", 0.7, "Баланса не хватает на продления в горизонте прогноза; чем ближе неоплаченное списание, тем сильнее")
def insufficient_funds( service, ctx ):
    f = ctx.funding.get(service.id)
    if not f or not f.shortfall:
        return None
    window, horizon = ctx.settings["expiringWindowDays"], ctx.settings["horizonDays"]
    wait = max((f.firstUnpaidAt - ctx.now).total_seconds() / 86400, 0)
    urgency = 1.0 if wait <= window else max(MIN_URGENCY, 1 - (1 - MIN_URGENCY) * (wait - window) / max(horizon - window, 1))
    return Signal(f.shortfall / f.due * urgency,
                  f"{service.name}: не хватает {eur(f.shortfall)}, первое неоплаченное продление {f.firstUnpaidAt:%d.%m} (через {days(wait)})")


@feature("expiring_without_autoprolong", "Истекает без автопродления", 0.6, "Скоро истекает, автопродление выключено (почасовые не учитываются)")
def expiring_without_autoprolong( service, ctx ):
    if not is_expiring(service, ctx):
        return None
    left = ctx.days_left(service)
    return Signal(min(1.0, 1 - left / expiring_window(service, ctx)), f"{service.name}: {expiry(left)}, автопродление выключено")


@feature("failed_payments", "Неоплаченные продления", 0.35, "Клиент недавно начинал продление, но не оплатил")
def failed_payments( service, ctx ):
    lookback = ctx.settings["paymentLookbackDays"]
    since = ctx.now - timedelta(days=lookback)
    prolongs = [t for t in ctx.transactions.get(service.id, [])
                if t.type == TransactionType.PROLONG and t.createdAt >= since]
    if service.status == ServiceStatus.PROLONG_WAIT:
        unpaid = [t for t in prolongs if not t.is_performed]
        if unpaid:
            prolongs.remove(max(unpaid, key=lambda t: t.createdAt))
    failed = len([t for t in prolongs if not t.is_performed])
    if not failed:
        return None
    return Signal(failed / len(prolongs),
                  f"{service.name}: не оплачено {failed} из {len(prolongs)} продлений за {lookback} дн.")


@feature("suspended", "Сервер выключен", 0.3, "Клиент платит, но не пользуется")
def suspended( service, ctx ):
    if service.status != ServiceStatus.SUSPENDED:
        return None
    return Signal(1.0, f"{service.name}: сервер выключен")


@feature("deleted_services", "Уже удалял услуги", 0.2, "Часть услуг клиента удалена: за неуплату или по его решению (почасовые не учитываются)")
def deleted_services( service, ctx ):
    # pochasovye servery sozdayut i udalyayut postoyanno: eto zhiznennyi cikl, a ne ottok
    kept = [s for s in ctx.services if s.paymentTerm != PaymentTerm.HOUR]
    lost = len([s for s in kept if s.status == ServiceStatus.DELETED])
    if not lost:
        return None
    return Signal(lost / len(kept), f"Клиент уже удалил {lost} из {len(kept)} услуг")


def age_days( moment, ctx ):
    return (ctx.now - moment).total_seconds() / 86400

@feature("new_customer", "Новый клиент", 0.25, "Все услуги моложе месяца: ранний отток в хостинге самый высокий")
def new_customer( service, ctx ):
    started = min((s.createdAt for s in ctx.services), default=None)
    if started is None:
        return None
    age = age_days(started, ctx)
    limit = ctx.settings["newCustomerDays"]
    if age < 0 or age >= limit:
        return None
    return Signal(1 - age / limit, f"Клиент с нами {days(age)}: первый месяц")


FIRST_PERIOD_SLACK = timedelta(days=1)

@feature("first_renewal", "Первое продление", 0.25,
         "Заканчивается первый оплаченный период услуги: здесь решают, оставить ли сервер (почасовые не учитываются)")
def first_renewal( service, ctx ):
    if service.status not in ( ServiceStatus.ACTIVE, ServiceStatus.SUSPENDED ):
        return None
    if service.expiresAt > next_period(service.createdAt, service.paymentTerm) + FIRST_PERIOD_SLACK:
        return None
    window = expiring_window(service, ctx)
    left = ctx.days_left(service)
    if window is None or left > window:
        return None
    return Signal(min(1.0, 1 - left / window), f"{service.name}: первое продление, {expiry(left)}")


@feature("long_tenure_autoprolong", "Давний клиент с автопродлением", 0.3,
         "Активная услуга старше полугода, автопродление включено, денег на два периода: снижает риск", kind="protective")
def long_tenure_autoprolong( service, ctx ):
    if service.status != ServiceStatus.ACTIVE or not service.autoProlong:
        return None
    age = age_days(service.createdAt, ctx)
    if age < ctx.settings["loyalTenureDays"] or ctx.availableFunds < 2 * service.price:
        return None
    return Signal(1.0, f"{service.name}: с нами {days(age)}, автопродление включено, денег на два периода")


EXPANSION_TENURE_DAYS = 90

@feature("recent_expansion", "Недавно заказал новую услугу", 0.3,
         "Давний клиент за последний месяц заказал новую живую услугу: вкладывается, а не уходит (почасовые не учитываются)",
         kind="protective")
def recent_expansion( service, ctx ):
    if service.status != ServiceStatus.ACTIVE or is_expiring(service, ctx):
        return None
    started = min((s.createdAt for s in ctx.services), default=None)
    if started is None or age_days(started, ctx) < EXPANSION_TENURE_DAYS:
        return None
    window = ctx.settings["newCustomerDays"]
    fresh = [s for s in ctx.services if s.is_live and s.paymentTerm != PaymentTerm.HOUR
             and 0 <= age_days(s.createdAt, ctx) <= window]
    if not fresh:
        return None
    last = max(fresh, key=lambda s: s.createdAt)
    return Signal(1.0, f"Клиент с нами {days(age_days(started, ctx))}, {days(age_days(last.createdAt, ctx))} назад заказал {last.name}")



LATE_MIN_PAYMENTS = 2   # меньше - еще не привычка
LATE_MIN_SHARE = 0.5    # для поздних оплат среди продлений
AUTO_BAND = timedelta(hours=1)  # дельта

def lateness( moment, service ):
    term = service.paymentTerm
    if term in ( PaymentTerm.HOUR, PaymentTerm.WEEK ):
        period = timedelta(hours=1) if term == PaymentTerm.HOUR else timedelta(weeks=1)
        r = (moment - service.createdAt) % period
        return r if r <= period / 2 else r - period
    boundary = service.createdAt
    while True:
        nxt = next_period(boundary, term)
        if nxt > moment:
            return moment - boundary if moment - boundary <= nxt - moment else moment - nxt
        boundary = nxt

def is_late_payment( delta, grace ):
    last_day = -timedelta(days=1) <= delta < -AUTO_BAND
    after_due = AUTO_BAND < delta <= grace
    return last_day or after_due

@feature("pays_late_but_pays", "Платит в последний момент", 0.3,
         "Раньше клиент оплачивал продления в последний день или после срока, но платил: ожидание оплаты для него привычно",
         kind="protective")
def pays_late_but_pays( service, ctx ):
    if service.status != ServiceStatus.PROLONG_WAIT and not is_expiring(service, ctx):
        return None
    grace = timedelta(days=ctx.settings["prolongWaitGraceDays"])
    total = late = 0
    for s in ctx.services:
        for t in ctx.transactions.get(s.id, []):
            if t.type != TransactionType.PROLONG or not t.is_performed or t.performedAt is None:
                continue
            total += 1
            if is_late_payment(lateness(t.performedAt, s), grace):
                late += 1
    if total < LATE_MIN_PAYMENTS or late / total < LATE_MIN_SHARE:
        return None
    return Signal(late / total,
                  f"Клиент {late} из {total} продлений оплачивал в последний день или после срока: ждёт оплаты, но обычно платит")


MANUAL_MIN_RENEWALS = 3   # men'she - eshche ne privychka
MANUAL_FULL_RENEWALS = 6  # s etogo chisla zashchita polnaya

@feature("reliable_manual_renewer", "Аккуратно продлевает вручную", 0.3,
         "Автопродление выключено, но услугу уже не раз продлевали вовремя и без неоплат: истечение для такого клиента не страшно",
         kind="protective")
def reliable_manual_renewer( service, ctx ):
    if not is_expiring(service, ctx):
        return None
    since = ctx.now - timedelta(days=ctx.settings["paymentLookbackDays"])
    grace = timedelta(days=ctx.settings["prolongWaitGraceDays"])
    prolongs = [t for t in ctx.transactions.get(service.id, []) if t.type == TransactionType.PROLONG]
    if any(not t.is_performed and t.createdAt >= since for t in prolongs):
        return None
    # pozdnie oplaty uzhe uchityvaet pays_late_but_pays
    onTime = len([t for t in prolongs if t.is_performed and t.performedAt is not None
                  and not is_late_payment(lateness(t.performedAt, service), grace)])
    if onTime < MANUAL_MIN_RENEWALS:
        return None
    return Signal(min(1.0, onTime / MANUAL_FULL_RENEWALS),
                  f"{service.name}: {onTime} продлений вручную вовремя, неоплат за {ctx.settings['paymentLookbackDays']} дн. нет")
