from __future__ import annotations

from datetime import datetime
from typing import Protocol

from backend.domain import (
    AccountDetails,
    ChurnChart,
    CustomerRisk,
    Session,
    Snapshot,
    Summary,
    Transition,
    User,
)


class ConflictError(Exception):
    pass


class Repository(Protocol):
    async def get_user_by_username(self, username: str) -> User | None: ...

    async def get_user(self, user_id: int) -> User | None: ...

    async def create_user(self, username: str, password_hash: str) -> User: ...

    async def create_session(self, session: Session) -> None: ...

    async def get_session(self, session_id: str) -> Session | None: ...

    async def delete_session(self, session_id: str) -> None: ...

    async def is_empty(self) -> bool:
        ...

    async def replace_snapshot(self, snapshot: Snapshot) -> None:
        ...

    async def get_snapshot(self) -> Snapshot: ...

    async def get_account(self, account_id: int) -> AccountDetails | None: ...

    async def save_risk(
        self, customers: list[CustomerRisk], summary: Summary, chart: ChurnChart | None = None
    ) -> None:
        ...

    async def get_summary(self) -> Summary | None: ...

    async def get_chart(self) -> ChurnChart | None: ...

    async def list_customers(
        self,
        *,
        search: str | None = None,
        levels: list[str] | None = None,
        sort_by: str = "accountId",
        sort_order: str = "asc",
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[CustomerRisk], int]:
        ...

    async def get_customer(self, account_id: int) -> CustomerRisk | None: ...

    async def append_journal(self, events: list[Transition]) -> None: ...

    async def list_journal(
        self,
        *,
        account_id: int | None = None,
        service_id: int | None = None,
        limit: int = 100,
    ) -> list[Transition]:
        ...

    async def observed_deletions(self) -> dict[int, datetime]:
        ...

    async def get_model_settings(self) -> dict:
        ...

    async def save_model_settings(self, settings: dict) -> None: ...


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
    def __init__(self, journal_limit: int = 50_000) -> None:
        from backend.domain import default_settings

        self._users: dict[int, User] = {}
        self._users_by_name: dict[str, int] = {}
        self._sessions: dict[str, Session] = {}

        self._snapshot = Snapshot(accounts=[], services=[], transactions=[])
        self._accounts_by_id: dict[int, AccountDetails] = {}
        self._customers: list[CustomerRisk] = []
        self._customers_by_id: dict[int, CustomerRisk] = {}
        self._summary: Summary | None = None
        self._chart: ChurnChart | None = None

        self._journal: list[Transition] = []
        self._journal_limit = journal_limit

        self._model_settings = default_settings()
        self._next_user_id = 1

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

    async def is_empty(self) -> bool:
        return not self._snapshot.accounts

    async def replace_snapshot(self, snapshot: Snapshot) -> None:
        self._snapshot = snapshot
        self._accounts_by_id = {a.id: a for a in snapshot.accounts}
        self._customers = []
        self._customers_by_id = {}
        self._summary = None
        self._chart = None

    async def get_snapshot(self) -> Snapshot:
        return self._snapshot

    async def get_account(self, account_id: int) -> AccountDetails | None:
        return self._accounts_by_id.get(account_id)

    async def save_risk(
        self, customers: list[CustomerRisk], summary: Summary, chart: ChurnChart | None = None
    ) -> None:
        self._customers = list(customers)
        self._customers_by_id = {c.accountId: c for c in customers}
        self._summary = summary
        self._chart = chart

    async def get_summary(self) -> Summary | None:
        return self._summary

    async def get_chart(self) -> ChurnChart | None:
        return self._chart

    async def list_customers(
        self,
        *,
        search: str | None = None,
        levels: list[str] | None = None,
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
        if levels:
            wanted = set(levels)
            items = [c for c in items if c.level in wanted]

        items = _sort_customers(items, sort_by, sort_order)
        total = len(items)
        return items[offset : offset + limit], total

    async def get_customer(self, account_id: int) -> CustomerRisk | None:
        return self._customers_by_id.get(account_id)

    async def append_journal(self, events: list[Transition]) -> None:
        if not events:
            return
        self._journal.extend(events)
        if len(self._journal) > self._journal_limit:
            del self._journal[: len(self._journal) - self._journal_limit]

    async def list_journal(
        self,
        *,
        account_id: int | None = None,
        service_id: int | None = None,
        limit: int = 100,
    ) -> list[Transition]:
        events = self._journal
        if account_id is not None:
            events = [e for e in events if e.ownerId == account_id]
        if service_id is not None:
            events = [e for e in events if e.serviceId == service_id]
        return list(reversed(events[-limit:])) if limit else list(reversed(events))

    async def observed_deletions(self) -> dict[int, datetime]:
        seen: dict[int, datetime] = {}
        for e in self._journal:
            if e.field == "status" and e.new == "deleted":
                seen[e.serviceId] = e.at
        return seen

    async def get_model_settings(self) -> dict:
        return _copy_settings(self._model_settings)

    async def save_model_settings(self, settings: dict) -> None:
        self._model_settings = _copy_settings(settings)


def _copy_settings(settings: dict) -> dict:
    copy = dict(settings)
    copy["weights"] = dict(settings.get("weights", {}))
    return copy


def _sort_customers(
    items: list[CustomerRisk], sort_by: str, sort_order: str
) -> list[CustomerRisk]:
    reverse = sort_order == "desc"
    key = _SORT_KEYS[sort_by]

    scored = [c for c in items if c.score is not None]
    unscored = [c for c in items if c.score is None]

    scored.sort(key=lambda c: (key(c), c.expectedLoss, c.accountId), reverse=reverse)
    return scored + sorted(unscored, key=lambda c: c.accountId)


_repository: Repository | None = None


def set_repository(repo: Repository) -> None:
    global _repository
    _repository = repo


def get_repository() -> Repository:
    if _repository is None:  # pragma: no cover
        raise RuntimeError("Repository не инициализирован: проверь lifespan в main.py")
    return _repository


def get_repository_or_none() -> Repository | None:
    return _repository
