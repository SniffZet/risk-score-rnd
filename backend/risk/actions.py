from dataclasses import dataclass

from backend.models import AccountDetails

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
    "new_customer": ("onboarding", "Онбординг",
        "Первый месяц: убедиться, что услуга настроена и используется, предложить помощь"),
    "first_renewal": ("first_renewal_check", "Связаться до первого продления",
        "Заканчивается первый период: спросить, всё ли работает, помочь с настройкой и напомнить о продлении"),
}

def recommend( reasons, account: AccountDetails, shortfall: int, bigSpender: int ):
    reasons = [r for r in reasons if getattr(r, "kind", "risk") != "protective"]
    if not reasons:
        return None
    top = reasons[0]
    if top.feature == "insufficient_funds" and account.totalReplenished >= bigSpender:
        return Action("vip_topup", "Персональное предложение на пополнение",
                      f"Клиент пополнил {eur(account.totalReplenished)} за всё время, а на продления не хватает {eur(shortfall)}: персональный бонус дешевле нового клиента")
    if top.feature == "insufficient_funds":
        return Action("topup_nudge", "Предложить пополнить баланс",
                      f"На продления в горизонте не хватает {eur(shortfall)}: предложить пополнение с бонусом")
    if top.feature in ACTIONS:
        return Action(*ACTIONS[top.feature])
    return Action("contact", "Связаться с клиентом", top.text)
