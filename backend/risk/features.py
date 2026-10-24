from dataclasses import dataclass, field
from datetime import datetime

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

def feature( uid: str, name: str, weight: float, description: str = "" ):
    def register( fn ):
        assert uid not in FEATURES, f'feature uid must be unique! [{uid}]x2'
        FEATURES[uid] = Feature( uid, name, weight, fn, description )
        return fn
    return register

######

def eur( cents ):
    return f"€{cents / 100:.2f}"

def days( d ):
    if d < 1:
        return f"{max(d, 0) * 24:.0f} ч"
    return f"{d:.0f} дн."


@feature("prolong_wait", "Ожидает оплаты", 0.9, "Период истёк, услугу удалят через несколько дней")
def prolong_wait( service, ctx ):
    if service.status != ServiceStatus.PROLONG_WAIT:
        return None
    grace = ctx.settings["prolongWaitGraceDays"]
    left = grace + ctx.days_left(service)
    if left <= 0:
        return Signal(1.0, f"{service.name}: срок ожидания оплаты истёк")
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
    return Signal(min(1.0, 1 - left / window), f"{service.name}: истекает через {days(left)}, автопродление выключено")


@feature("failed_payments", "Неоплаченные продления", 0.35, "Клиент начинал продление, но не оплатил")
def failed_payments( service, ctx ):
    prolongs = [t for t in ctx.transactions.get(service.id, []) if t.type == TransactionType.PROLONG]
    failed = len([t for t in prolongs if not t.is_performed])
    if not failed:
        return None
    return Signal(failed / len(prolongs), f"{service.name}: не оплачено {failed} из {len(prolongs)} продлений")


@feature("suspended", "Сервер выключен", 0.3, "Клиент платит, но не пользуется")
def suspended( service, ctx ):
    if service.status != ServiceStatus.SUSPENDED:
        return None
    return Signal(1.0, f"{service.name}: сервер выключен")


# na urovne akkaunta, odinakovyi na vseh uslugah
@feature("churn_history", "Уже уходил", 0.2, "Часть услуг клиента уже удалена или заблокирована")
def churn_history( service, ctx ):
    lost = len([s for s in ctx.services if not s.is_live])
    if not lost:
        return None
    return Signal(lost / len(ctx.services), f"Клиент уже потерял {lost} из {len(ctx.services)} услуг")
