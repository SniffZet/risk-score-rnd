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
    shortfall: int = 0 # skolko ne hvataet
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
    kind: str = "risk" # risk - povyshaet risk, protective - snizhaet

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
    # 0.6 v pervyi den' -> 1.0 v den' udaleniya
    return Signal(0.6 + 0.4 * (1 - left / grace), f"{service.name}: ждёт оплаты, до удаления {days(left)}")


@feature("insufficient_funds", "Не хватает средств", 0.7, "Баланса не хватает на продления в горизонте прогноза")
def insufficient_funds( service, ctx ):
    f = ctx.funding.get(service.id)
    if not f or not f.shortfall:
        return None
    return Signal(f.shortfall / f.due,
                  f"{service.name}: не хватает {eur(f.shortfall)}, первое неоплаченное продление {f.firstUnpaidAt:%d.%m}")


@feature("expiring_without_autoprolong", "Истекает без автопродления", 0.6, "Скоро истекает, автопродление выключено")
def expiring_without_autoprolong( service, ctx ):
    if service.autoProlong or service.status not in ( ServiceStatus.ACTIVE, ServiceStatus.SUSPENDED ):
        return None
    window = ctx.settings["expiringWindowDays"]
    left = ctx.days_left(service)
    if left > window:
        return None
    return Signal(min(1.0, 1 - left / window), f"{service.name}: {expiry(left)}, автопродление выключено")


@feature("failed_payments", "Неоплаченные продления", 0.35, "Клиент недавно начинал продление, но не оплатил")
def failed_payments( service, ctx ):
    lookback = ctx.settings["paymentLookbackDays"]
    since = ctx.now - timedelta(days=lookback)
    # tol'ko svezhie popytki: staraya istoriya shumit, a ne predskazyvaet
    prolongs = [t for t in ctx.transactions.get(service.id, [])
                if t.type == TransactionType.PROLONG and t.createdAt >= since]
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


@feature("deleted_services", "Уже удалял услуги", 0.2, "Часть услуг клиента удалена: за неуплату или по его решению")
def deleted_services( service, ctx ):
    lost = len([s for s in ctx.services if s.status == ServiceStatus.DELETED])
    if not lost:
        return None
    return Signal(lost / len(ctx.services), f"Клиент уже удалил {lost} из {len(ctx.services)} услуг")


@feature("blocked_services", "Есть заблокированные услуги", 0.15, "Часть услуг заблокирована платформой: конфликт, а не неуплата")
def blocked_services( service, ctx ):
    blocked = len([s for s in ctx.services if s.status == ServiceStatus.BLOCKED])
    if not blocked:
        return None
    return Signal(blocked / len(ctx.services), f"У клиента заблокировано {blocked} из {len(ctx.services)} услуг")


def age_days( moment, ctx ):
    return (ctx.now - moment).total_seconds() / 86400

@feature("never_renewed", "Ни разу не продлевал", 0.3, "Услуга старше одного периода, выполненных продлений нет, автопродление выключено")
def never_renewed( service, ctx ):
    if service.autoProlong:
        return None
    age = age_days(service.createdAt, ctx)
    if age < TERM_DAYS[service.paymentTerm]:
        return None
    renewed = [t for t in ctx.transactions.get(service.id, []) if t.type == TransactionType.PROLONG and t.is_performed]
    if renewed:
        return None
    return Signal(1.0, f"{service.name}: за {days(age)} ни одного продления, автопродление выключено")


@feature("big_spender_drained", "Крупный клиент на нуле", 0.35, "Много пополнял за всё время, а на ближайшее списание не хватает")
def big_spender_drained( service, ctx ):
    a = ctx.account
    if a.totalReplenished < ctx.settings["bigSpenderThreshold"] or service.price <= 0:
        return None
    if ctx.availableFunds >= service.price:
        return None
    return Signal(1 - ctx.availableFunds / service.price,
                  f"Пополнил {eur(a.totalReplenished)} за всё время, доступно {eur(ctx.availableFunds)} при цене {eur(service.price)}")


@feature("new_customer", "Новый клиент", 0.25, "Все услуги моложе месяца: ранний отток в хостинге самый высокий")
def new_customer( service, ctx ):
    started = min((s.createdAt for s in ctx.services), default=None)
    if started is None:
        return None
    age = age_days(started, ctx)
    limit = ctx.settings["newCustomerDays"]
    # otricatel'nyi vozrast - oshibka v dannyh (data sozdaniya v budushchem), ne signal
    if age < 0 or age >= limit:
        return None
    return Signal(1 - age / limit, f"Клиент с нами {days(age)}: первый месяц")


CLUSTER_WINDOW = timedelta(days=3)

@feature("renewal_cluster", "Несколько продлений подряд", 0.25, "Несколько услуг продлеваются в одни дни на сумму больше доступных денег")
def renewal_cluster( service, ctx ):
    mine = max(service.expiresAt, ctx.now)
    cluster = [s for s in ctx.services if s.is_live and abs(max(s.expiresAt, ctx.now) - mine) <= CLUSTER_WINDOW]
    if len(cluster) < 2:
        return None
    total = sum(s.price for s in cluster)
    if total <= 0 or total <= ctx.availableFunds:
        return None
    first, last = min(max(s.expiresAt, ctx.now) for s in cluster), max(max(s.expiresAt, ctx.now) for s in cluster)
    return Signal((total - ctx.availableFunds) / total,
                  f"{len(cluster)} услуги продлеваются {first:%d.%m}–{last:%d.%m} на {eur(total)}, доступно {eur(ctx.availableFunds)}")


@feature("long_tenure_autoprolong", "Давний клиент с автопродлением", 0.3,
         "Активная услуга старше полугода, автопродление включено, денег на два периода: снижает риск", kind="protective")
def long_tenure_autoprolong( service, ctx ):
    if service.status != ServiceStatus.ACTIVE or not service.autoProlong:
        return None
    age = age_days(service.createdAt, ctx)
    if age < ctx.settings["loyalTenureDays"] or ctx.availableFunds < 2 * service.price:
        return None
    return Signal(1.0, f"{service.name}: с нами {days(age)}, автопродление включено, денег на два периода")
