from dataclasses import dataclass

from backend.models import AccountDetails, BonusState

@dataclass
class Action:
    code: str
    title: str
    text: str

def eur( cents ):
    return f"€{cents / 100:.2f}"

ACTIONS = {
    "prolong_wait": ("remind_payment", "Напомнить об оплате",
        "Услуга ждёт оплаты и будет удалена: напоминание с прямой ссылкой на оплату и промокодом на пополнение"),
    "expiring_without_autoprolong": ("enable_autoprolong", "Предложить включить автопродление",
        "Услуга скоро истекает, а автопродление выключено: письмо с кнопкой «включить» спасает продление"),
    "failed_payments": ("check_payment", "Проверить способ оплаты",
        "Продления не проходят: возможно, проблема с картой или платёжкой, нужна помощь поддержки"),
    "suspended": ("ask_why_off", "Выяснить причину выключения",
        "Сервер выключен, но оплачивается: предложить паузу тарифа, даунгрейд или помощь с настройкой"),
    "deleted_services": ("winback", "Удержание через поддержку",
        "Клиент уже удалял услуги: персональное предложение до истечения оставшихся"),
    "blocked_services": ("resolve_block", "Разобрать блокировку",
        "Есть заблокированная услуга: связаться и снять конфликт, иначе уйдут и остальные"),
    "never_renewed": ("enable_autoprolong", "Предложить включить автопродление",
        "Клиент ни разу не продлевал услугу вручную: автопродление снимает риск просто забыть"),
    "big_spender_drained": ("vip_topup", "Персональное предложение на пополнение",
        "Клиент много платил и остался без денег: персональный бонус за пополнение дешевле, чем новый клиент"),
    "new_customer": ("onboarding", "Онбординг",
        "Первый месяц: убедиться, что услуга настроена и используется, предложить помощь"),
    "renewal_cluster": ("warn_cluster", "Предупредить о серии списаний",
        "Несколько услуг продлеваются в одни дни: заранее сказать, сколько нужно на балансе"),
}

def recommend( reasons, account: AccountDetails, shortfall: int ):
    reasons = [r for r in reasons if getattr(r, "kind", "risk") != "protective"]
    if not reasons:
        return None
    fired = { r.feature for r in reasons }

    if "insufficient_funds" in fired and account.bonusState == BonusState.LOCKED and account.bonusBalance > 0:
        return Action("unlock_bonus", "Разблокировать бонусы",
                      f"Бонусов {eur(account.bonusBalance)} хватит закрыть часть нехватки {eur(shortfall)} на продления: разблокировка дешевле скидки")
    top = reasons[0]
    if top.feature == "insufficient_funds":
        return Action("topup_nudge", "Предложить пополнить баланс",
                      f"На продления в горизонте не хватает {eur(shortfall)}: предложить пополнение с бонусом")
    if top.feature in ACTIONS:
        return Action(*ACTIONS[top.feature])
    return Action("contact", "Связаться с клиентом", top.text)
