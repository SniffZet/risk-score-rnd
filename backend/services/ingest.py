from __future__ import annotations

from typing import Any

from backend.domain import Snapshot
from backend.services.normalize import (
    SnapshotError,
    _format_errors,
    parse_accounts,
    parse_services,
    parse_transactions,
)

SECTIONS = ("accounts", "services", "transactions")


def merge_snapshot(current: Snapshot, raw: Any) -> tuple[Snapshot, dict[str, int]]:
    if not isinstance(raw, dict):
        raise SnapshotError("ожидался JSON-объект с полями accounts/services/transactions")

    incoming: dict[str, list] = {}
    for section in SECTIONS:
        items = raw.get(section) or []
        if not isinstance(items, list):
            raise SnapshotError(f"раздел '{section}' должен быть массивом")
        incoming[section] = items
    if not any(incoming.values()):
        raise SnapshotError("в запросе нет ни одной записи")

    errors: list[str] = []

    accounts = {a.id: a for a in current.accounts}
    emails = {a.email: a.id for a in current.accounts}
    for account in parse_accounts(incoming["accounts"], errors):
        owner = emails.get(account.email)
        if owner is not None and owner != account.id:
            errors.append(f"accounts: адрес {account.email!r} уже у аккаунта {owner}")
            continue
        previous = accounts.get(account.id)
        if previous is not None:
            emails.pop(previous.email, None)
        accounts[account.id] = account
        emails[account.email] = account.id

    services = {s.id: s for s in current.services}
    for service in parse_services(incoming["services"], set(accounts), errors):
        services[service.id] = service

    transactions = {t.id: t for t in current.transactions}
    for transaction in parse_transactions(incoming["transactions"], set(services), errors):
        transactions[transaction.id] = transaction

    if errors:
        total = sum(len(items) for items in incoming.values())
        raise SnapshotError(_format_errors(errors, total))

    merged = Snapshot(
        accounts=list(accounts.values()),
        services=list(services.values()),
        transactions=list(transactions.values()),
    )
    return merged, {section: len(items) for section, items in incoming.items()}
