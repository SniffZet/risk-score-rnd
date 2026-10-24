"""Слой хранения: контракт + реализация в памяти.

Зачем так. Базу делает человек со стороны модели, и он же владеет схемой
(``risk-score-rnd-main/data/001_schema.up.sql``). Чтобы его работа свелась к
«написать один класс», весь остальной код общается только с протоколом
``Repository`` и ничего не знает про SQL.

Позже достаточно добавить ``app/repository_sql.py`` с классом, реализующим
те же методы, и переключить ``STORAGE_BACKEND=sql``. Ни роутеры, ни сервисы
менять не придётся.

Хранилище держит две вещи:
1. данные организаторов — ``Snapshot`` (accounts / services / transactions);
2. результаты скоринга — список ``CustomerRisk`` и ``Summary``.

Результаты хранятся отдельно, потому что их считает модель, а API должен
уметь фильтровать, сортировать и пагинировать по ним, не пересчитывая модель
на каждый запрос.
"""
from __future__ import annotations

from typing import Protocol

from backend.domain import (
    CustomerRisk,
    ServiceStatus,
    Session,
    Snapshot,
    Summary,
    User,
)


class ConflictError(Exception):
    """Сущность уже существует (например, username занят)."""


class Repository(Protocol):
    """Контракт хранилища. Все методы асинхронные."""

    # --- пользователи и сессии (наша часть, к модели отношения не имеет) ---
    async def get_user_by_username(self, username: str) -> User | None: ...

    async def get_user(self, user_id: int) -> User | None: ...

    async def create_user(self, username: str, password_hash: str) -> User: ...

    async def create_session(self, session: Session) -> None: ...

    async def get_session(self, session_id: str) -> Session | None: ...

    async def delete_session(self, session_id: str) -> None: ...

    # --- данные организаторов ----------------------------------------------
    async def is_empty(self) -> bool:
        """True, если данных ещё нет и нужна первичная загрузка."""
        ...

    async def replace_snapshot(self, snapshot: Snapshot) -> None:
        """Атомарно заменить все данные (в SQL — одной транзакцией)."""
        ...

    async def get_snapshot(self) -> Snapshot: ...

    # --- результаты скоринга -------------------------------------------------
    async def save_risk(
        self, customers: list[CustomerRisk], summary: Summary
    ) -> None:
        """Сохранить результат работы модели (вызывается из recompute)."""
        ...

    async def get_summary(self) -> Summary | None: ...

    async def list_customers(
        self,
        *,
        search: str | None = None,
        level: str | None = None,
        sort_by: str = "accountId",
        sort_order: str = "asc",
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[CustomerRisk], int]:
        """Вернуть (страница, всего_подходящих).

        В SQL-реализации это WHERE / ORDER BY / LIMIT — без выгрузки всей
        таблицы в память.
        """
        ...

    async def get_customer(self, account_id: int) -> CustomerRisk | None: ...

    async def churn_buckets(self, grace_days: int) -> dict[str, dict[str, int]]:
        """Агрегат по дням: {"2026-01-01": {"deleted": 0, "expected": 2}}.

        Считается на стороне хранилища (в SQL — GROUP BY), чтобы не тянуть
        все услуги в память.
        """
        ...

    # --- настройки модели ---------------------------------------------------
    async def get_model_settings(self) -> dict:
        """Текущие настройки модели (уже слитые с настройками по умолчанию)."""
        ...

    async def save_model_settings(self, settings: dict) -> None: ...


#: Поля, доступные для сортировки. Совпадают с именами в ответе API.
SORT_FIELDS = (
    "accountId",
    "email",
    "balance",
    "totalReplenished",
    "score",
    "expectedLoss",
    "revenue",
    "loyalty",
)

_SORT_KEYS = {
    "accountId": lambda c: c.accountId,
    "email": lambda c: (c.email or "").lower(),
    "balance": lambda c: c.balance,
    "totalReplenished": lambda c: c.totalReplenished,
    "score": lambda c: c.score,
    "expectedLoss": lambda c: c.expectedLoss,
    "revenue": lambda c: c.revenue,
    "loyalty": lambda c: c.loyalty,
}


class MemoryRepository:
    """Хранилище в оперативной памяти.

    Подходит для разработки, тестов и демо. Данные теряются при рестарте —
    поэтому при старте выполняется первичная загрузка из data.json.

    Блокировок нет намеренно: все методы работают со структурами в памяти и
    не содержат точек ожидания, поэтому в рамках одного event loop они
    атомарны. Асинхронная блокировка только привязала бы хранилище к
    конкретному циклу событий и сломала бы тесты и встраивание.
    """

    def __init__(self) -> None:
        from backend.domain import default_settings

        self._users: dict[int, User] = {}
        self._users_by_name: dict[str, int] = {}
        self._sessions: dict[str, Session] = {}

        self._snapshot = Snapshot(accounts=[], services=[], transactions=[])
        self._customers: list[CustomerRisk] = []
        self._customers_by_id: dict[int, CustomerRisk] = {}
        self._summary: Summary | None = None

        self._model_settings = default_settings()
        self._next_user_id = 1

    # --- пользователи и сессии ---------------------------------------------
    async def get_user_by_username(self, username: str) -> User | None:
        user_id = self._users_by_name.get(username)
        return self._users.get(user_id) if user_id is not None else None

    async def get_user(self, user_id: int) -> User | None:
        return self._users.get(user_id)

    async def create_user(self, username: str, password_hash: str) -> User:
        if username in self._users_by_name:
            raise ConflictError(f"пользователь '{username}' уже существует")
        user = User(id=self._next_user_id, username=username, password_hash=password_hash)
        self._users[user.id] = user
        self._users_by_name[username] = user.id
        self._next_user_id += 1
        return user

    async def create_session(self, session: Session) -> None:
        self._sessions[session.id] = session

    async def get_session(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)

    async def delete_session(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    # --- данные организаторов ----------------------------------------------
    async def is_empty(self) -> bool:
        return not self._snapshot.accounts

    async def replace_snapshot(self, snapshot: Snapshot) -> None:
        """Подменить данные и сбросить результаты прошлого скоринга.

        Сброс обязателен: оценки относились к старым данным, и показывать их
        вместе с новыми — значит врать пользователю. Пересчёт выполнит
        вызывающий (roутер загрузки или цикл по таймеру).
        """
        self._snapshot = snapshot
        self._customers = []
        self._customers_by_id = {}
        self._summary = None

    async def get_snapshot(self) -> Snapshot:
        return self._snapshot

    # --- результаты скоринга -------------------------------------------------
    async def save_risk(self, customers: list[CustomerRisk], summary: Summary) -> None:
        self._customers = list(customers)
        self._customers_by_id = {c.accountId: c for c in customers}
        self._summary = summary

    async def get_summary(self) -> Summary | None:
        return self._summary

    async def list_customers(
        self,
        *,
        search: str | None = None,
        level: str | None = None,
        sort_by: str = "accountId",
        sort_order: str = "asc",
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[CustomerRisk], int]:
        if sort_by not in SORT_FIELDS:
            raise ValueError(f"неизвестное поле сортировки: {sort_by}")

        items = list(self._customers)

        if search:
            needle = search.lower()
            items = [c for c in items if needle in (c.email or "").lower()]
        if level:
            items = [c for c in items if c.level == level]

        items = _sort_customers(items, sort_by, sort_order)
        total = len(items)
        return items[offset : offset + limit], total

    async def get_customer(self, account_id: int) -> CustomerRisk | None:
        return self._customers_by_id.get(account_id)

    async def churn_buckets(self, grace_days: int) -> dict[str, dict[str, int]]:
        from datetime import timedelta

        buckets: dict[str, dict[str, int]] = {}
        for service in self._snapshot.services:
            if service.status == ServiceStatus.DELETED:
                day = service.expiresAt.date().isoformat()
                buckets.setdefault(day, {"deleted": 0, "expected": 0})["deleted"] += 1
            elif service.status == ServiceStatus.PROLONG_WAIT:
                day = (service.expiresAt + timedelta(days=grace_days)).date().isoformat()
                buckets.setdefault(day, {"deleted": 0, "expected": 0})["expected"] += 1
        return buckets

    # --- настройки модели ---------------------------------------------------
    async def get_model_settings(self) -> dict:
        return _copy_settings(self._model_settings)

    async def save_model_settings(self, settings: dict) -> None:
        self._model_settings = _copy_settings(settings)


def _copy_settings(settings: dict) -> dict:
    """Копия настроек, чтобы вызывающий не мог изменить состояние хранилища."""
    copy = dict(settings)
    copy["weights"] = dict(settings.get("weights", {}))
    return copy


def _sort_customers(
    items: list[CustomerRisk], sort_by: str, sort_order: str
) -> list[CustomerRisk]:
    """Сортировка с предсказуемым поведением для клиентов без оценки.

    Клиенты без score (``no_data``) всегда оказываются в конце списка — и при
    asc, и при desc. Иначе на первой странице «топа риска» оказались бы
    записи, о которых мы вообще ничего не знаем.
    """
    reverse = sort_order == "desc"
    key = _SORT_KEYS[sort_by]

    scored = [c for c in items if c.score is not None]
    unscored = [c for c in items if c.score is None]

    scored.sort(key=lambda c: (key(c), c.accountId), reverse=reverse)
    return scored + sorted(unscored, key=lambda c: c.accountId)


#: Синглтон, который создаёт приложение при старте.
_repository: Repository | None = None


def set_repository(repo: Repository) -> None:
    global _repository
    _repository = repo


def get_repository() -> Repository:
    if _repository is None:  # pragma: no cover - защита от неверной сборки
        raise RuntimeError("Repository не инициализирован: проверь lifespan в main.py")
    return _repository


def get_repository_or_none() -> Repository | None:
    """Текущее хранилище, если оно уже установлено (нужно тестам и lifespan)."""
    return _repository
