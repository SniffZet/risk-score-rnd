from __future__ import annotations

import math
import time
from collections import deque
from dataclasses import dataclass
from threading import Lock
from typing import Callable

from prometheus_client import Counter
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

rejections = Counter(
    "churn_rate_limit_rejections_total",
    "Запросы, отклонённые ограничением частоты",
    ["scope"],
)


@dataclass(frozen=True)
class Decision:
    retry_after: int = 0
    scope: str = "api"


class RateLimiter:
    """Per-IP sliding windows; state belongs to one application process."""

    def __init__(
        self, *, window: int, api_limit: int, login_limit: int,
        max_clients: int = 10_000, clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.window = window
        self.api_limit = api_limit
        self.login_limit = login_limit
        self.max_clients = max_clients
        self.clock = clock
        self._clients: dict[str, dict[str, deque[float]]] = {}
        self._next_cleanup = 0.0
        self._lock = Lock()

    def check(self, client: str, *, login: bool = False) -> Decision:
        with self._lock:
            now = self.clock()
            cutoff = now - self.window
            if now >= self._next_cleanup:
                for address, windows in list(self._clients.items()):
                    if all(not hits or hits[-1] <= cutoff for hits in windows.values()):
                        del self._clients[address]
                self._next_cleanup = now + self.window

            if client not in self._clients:
                if len(self._clients) >= self.max_clients:
                    return Decision(max(1, math.ceil(self._next_cleanup - now)), "capacity")
                self._clients[client] = {"api": deque(), "login": deque()}
            windows = self._clients[client]
            budgets = [("api", self.api_limit)]
            if login:
                budgets.append(("login", self.login_limit))
            blocked = []
            for name, limit in budgets:
                hits = windows[name]
                while hits and hits[0] <= cutoff:
                    hits.popleft()
                if len(hits) >= limit:
                    blocked.append(Decision(max(1, math.ceil(hits[0] + self.window - now)), name))
            if blocked:
                return max(blocked, key=lambda decision: decision.retry_after)
            for name, _ in budgets:
                windows[name].append(now)
            return Decision()


class RateLimitMiddleware:
    def __init__(self, app: ASGIApp, *, limiter: RateLimiter, prefix: str) -> None:
        self.app = app
        self.limiter = limiter
        self.prefix = prefix.rstrip("/")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "")
        if (
            scope["type"] != "http" or scope["method"] == "OPTIONS"
            or not (path == self.prefix or path.startswith(self.prefix + "/"))
        ):
            await self.app(scope, receive, send)
            return
        peer = scope.get("client")
        client = peer[0] if peer else "unknown"
        decision = self.limiter.check(
            client,
            login=path.rstrip("/") == self.prefix + "/auth/login",
        )
        if decision.retry_after:
            rejections.labels(scope=decision.scope).inc()
            message = (
                "Слишком много попыток входа. Повторите позже."
                if decision.scope == "login"
                else "Слишком много запросов. Повторите позже."
            )
            response = JSONResponse(
                {"detail": message, "retryAfter": decision.retry_after},
                status_code=429,
                headers={"Retry-After": str(decision.retry_after), "Cache-Control": "no-store"},
            )
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)
