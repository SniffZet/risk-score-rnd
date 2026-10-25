from __future__ import annotations

from dataclasses import fields
from typing import Any

from backend.domain import (
    AccountDetails,
    BonusState,
    PaymentTerm,
    ServiceDetails,
    ServiceStatus,
    Snapshot,
    TransactionDetails,
    TransactionStatus,
    TransactionType,
    as_utc,
    parsetime,
)

AMOUNT_MIN = 0

MAX_REPORTED_ERRORS = 5


class SnapshotError(ValueError):
    pass


def _require_obj(item: Any, where: str) -> dict:
    if not isinstance(item, dict):
        raise SnapshotError(f"{where}: ожидался объект, получено {type(item).__name__}")
    return item


def _get(obj: dict, key: str, where: str, default: Any = ...) -> Any:
    if key in obj and obj[key] is not None:
        return obj[key]
    if default is not ...:
        return default
    raise SnapshotError(f"{where}: отсутствует обязательное поле '{key}'")


def _int(value: Any, where: str, field: str, *, minimum: int | None = None,
         maximum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise SnapshotError(f"{where}.{field}: ожидалось целое число, получено {value!r}")
    if minimum is not None and value < minimum:
        raise SnapshotError(f"{where}.{field}: значение {value} меньше допустимого {minimum}")
    if maximum is not None and value > maximum:
        raise SnapshotError(f"{where}.{field}: значение {value} больше допустимого {maximum}")
    return value


def _bool(value: Any, where: str, field: str) -> bool:
    if not isinstance(value, bool):
        raise SnapshotError(f"{where}.{field}: ожидалось true/false, получено {value!r}")
    return value


def _enum(value: Any, enum_cls, where: str, field: str):
    try:
        return enum_cls(value)
    except ValueError:
        allowed = ", ".join(e.value for e in enum_cls)
        raise SnapshotError(
            f"{where}.{field}: недопустимое значение {value!r}; допустимо: {allowed}"
        ) from None


def _time(value: Any, where: str, field: str):
    try:
        parsed = parsetime(value) if isinstance(value, str) else value
    except (ValueError, TypeError):
        parsed = None

    if parsed is None:
        raise SnapshotError(f"{where}.{field}: не удалось разобрать дату {value!r}")
    if not hasattr(parsed, "tzinfo"):
        raise SnapshotError(f"{where}.{field}: ожидалась дата, получено {value!r}")
    return as_utc(parsed)


def _build(model, clean: dict, where: str):
    expected = {f.name for f in fields(model)}
    missing = expected - clean.keys()
    if missing:  # pragma: no cover
        raise SnapshotError(f"{where}: не заполнены поля {sorted(missing)}")
    try:
        return model.format_dict(clean)
    except (KeyError, TypeError, ValueError) as exc:
        raise SnapshotError(f"{where}: {exc}") from exc


def _format_errors(errors: list[str], total: int) -> str:
    head = "; ".join(errors[:MAX_REPORTED_ERRORS])
    hidden = len(errors) - MAX_REPORTED_ERRORS
    suffix = f" (и ещё {hidden})" if hidden > 0 else ""
    return f"ошибки валидации ({len(errors)} из {total} записей): {head}{suffix}"


def parse_accounts(items: list[Any], errors: list[str]) -> list[AccountDetails]:
    accounts: list[AccountDetails] = []
    seen: set[str] = set()

    for index, raw in enumerate(items):
        where = f"accounts[{index}]"
        try:
            obj = _require_obj(raw, where)
            email = _get(obj, "email", where)
            if not isinstance(email, str) or not email.strip():
                raise SnapshotError(f"{where}.email: ожидалась непустая строка")
            if email in seen:
                raise SnapshotError(f"{where}.email: адрес {email!r} уже встречается")
            seen.add(email)

            accounts.append(
                _build(AccountDetails, {
                    "id": _int(_get(obj, "id", where), where, "id"),
                    "email": email,
                    "balance": _int(_get(obj, "balance", where, 0), where, "balance", minimum=0),
                    "withdrawBalance": _int(
                        _get(obj, "withdrawBalance", where, 0), where, "withdrawBalance", minimum=0
                    ),
                    "totalReplenished": _int(
                        _get(obj, "totalReplenished", where, 0),
                        where,
                        "totalReplenished",
                        minimum=0,
                    ),
                    "bonusBalance": _int(
                        _get(obj, "bonusBalance", where, 0), where, "bonusBalance", minimum=0
                    ),
                    "bonusState": _enum(
                        _get(obj, "bonusState", where, BonusState.LOCKED.value),
                        BonusState,
                        where,
                        "bonusState",
                    ),
                }, where)
            )
        except SnapshotError as exc:
            errors.append(str(exc))

    return accounts


def parse_services(
    items: list[Any], known_accounts: set[int], errors: list[str]
) -> list[ServiceDetails]:
    services: list[ServiceDetails] = []

    for index, raw in enumerate(items):
        where = f"services[{index}]"
        try:
            obj = _require_obj(raw, where)
            name = _get(obj, "name", where)
            if not isinstance(name, str) or not name.strip():
                raise SnapshotError(f"{where}.name: ожидалась непустая строка, получено {name!r}")

            owner_id = _int(_get(obj, "ownerId", where), where, "ownerId")
            if owner_id not in known_accounts:
                raise SnapshotError(
                    f"{where}.ownerId: аккаунт {owner_id} не существует"
                )

            created_at = _time(_get(obj, "createdAt", where), where, "createdAt")
            expires_at = _time(_get(obj, "expiresAt", where), where, "expiresAt")
            if expires_at < created_at:
                raise SnapshotError(
                    f"{where}.expiresAt: срок истечения раньше даты создания"
                )

            services.append(
                _build(ServiceDetails, {
                    "id": _int(_get(obj, "id", where), where, "id"),
                    "name": name,
                    "ownerId": owner_id,
                    "paymentTerm": _enum(
                        _get(obj, "paymentTerm", where), PaymentTerm, where, "paymentTerm"
                    ),
                    "autoProlong": _bool(
                        _get(obj, "autoProlong", where, False), where, "autoProlong"
                    ),
                    "createdAt": created_at.isoformat(),
                    "expiresAt": expires_at.isoformat(),
                    "status": _enum(_get(obj, "status", where), ServiceStatus, where, "status"),
                    "price": _int(_get(obj, "price", where), where, "price", minimum=0),
                }, where)
            )
        except SnapshotError as exc:
            errors.append(str(exc))

    return services


def parse_transactions(
    items: list[Any], known_services: set[int], errors: list[str]
) -> list[TransactionDetails]:
    transactions: list[TransactionDetails] = []

    for index, raw in enumerate(items):
        where = f"transactions[{index}]"
        try:
            obj = _require_obj(raw, where)

            service_id = _int(_get(obj, "serviceId", where), where, "serviceId")
            if service_id not in known_services:
                raise SnapshotError(
                    f"{where}.serviceId: услуга {service_id} не существует"
                )

            created_at = _time(_get(obj, "createdAt", where), where, "createdAt")
            status = _enum(_get(obj, "status", where), TransactionStatus, where, "status")

            raw_performed = obj.get("performedAt")
            if status == TransactionStatus.PERFORMED:
                if raw_performed is None:
                    raise SnapshotError(
                        f"{where}.performedAt: обязателен для статуса 'performed'"
                    )
                performed_at = _time(raw_performed, where, "performedAt")
                if performed_at < created_at:
                    raise SnapshotError(
                        f"{where}.performedAt: раньше даты создания транзакции"
                    )
            else:
                if raw_performed is not None:
                    raise SnapshotError(
                        f"{where}.performedAt: должен быть null для статуса 'not_performed'"
                    )
                performed_at = None

            transactions.append(
                _build(TransactionDetails, {
                    "id": _int(_get(obj, "id", where), where, "id"),
                    "amount": _int(
                        _get(obj, "amount", where),
                        where,
                        "amount",
                        minimum=AMOUNT_MIN,
                    ),
                    "status": status,
                    "performedAt": performed_at.isoformat() if performed_at else None,
                    "createdAt": created_at.isoformat(),
                    "type": _enum(_get(obj, "type", where), TransactionType, where, "type"),
                    "serviceId": service_id,
                }, where)
            )
        except SnapshotError as exc:
            errors.append(str(exc))

    return transactions


def parse_snapshot(raw: Any) -> Snapshot:
    if not isinstance(raw, dict):
        raise SnapshotError("ожидался JSON-объект с полями accounts/services/transactions")

    accounts_raw = raw.get("accounts")
    if accounts_raw is None:
        raise SnapshotError("в файле нет раздела 'accounts'")
    if not isinstance(accounts_raw, list):
        raise SnapshotError("раздел 'accounts' должен быть массивом")
    if not accounts_raw:
        raise SnapshotError("в файле нет ни одного аккаунта")

    services_raw = raw.get("services") or []
    transactions_raw = raw.get("transactions") or []
    if not isinstance(services_raw, list):
        raise SnapshotError("раздел 'services' должен быть массивом")
    if not isinstance(transactions_raw, list):
        raise SnapshotError("раздел 'transactions' должен быть массивом")

    errors: list[str] = []

    accounts = parse_accounts(accounts_raw, errors)
    known_accounts = {a.id for a in accounts}

    services = parse_services(services_raw, known_accounts, errors)
    known_services = {s.id for s in services}

    transactions = parse_transactions(transactions_raw, known_services, errors)

    if errors:
        total = len(accounts_raw) + len(services_raw) + len(transactions_raw)
        raise SnapshotError(_format_errors(errors, total))

    return Snapshot(accounts=accounts, services=services, transactions=transactions)
