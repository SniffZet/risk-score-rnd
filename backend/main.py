from __future__ import annotations

import asyncio
import hmac
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from backend.config import settings
from backend.domain import utcnow
from backend.repository import (
    MemoryRepository,
    Repository,
    get_repository_or_none,
    set_repository,
)
from backend.repository_file import FileRepository
from backend.rate_limit import RateLimiter, RateLimitMiddleware
from backend.routers import analytics, auth, customers, events, model_settings, oidc, source
from backend.schemas import RateLimitOut
from backend.security import hash_password
from backend.services.recompute import recompute
from backend.services.seed import seed_if_empty
from backend.state import state

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)
logger = logging.getLogger("churn")


def build_repository() -> Repository:
    if settings.STORAGE_BACKEND == "file":
        return FileRepository(settings.DATA_DIR, journal_limit=settings.JOURNAL_MAX_EVENTS)
    if settings.STORAGE_BACKEND != "memory":
        raise RuntimeError(
            f"STORAGE_BACKEND={settings.STORAGE_BACKEND!r} не поддерживается: допустимы file и memory"
        )
    return MemoryRepository(journal_limit=settings.JOURNAL_MAX_EVENTS)


async def ensure_admin(repository: Repository) -> None:
    existing = await repository.get_user_by_username(settings.ADMIN_USERNAME)
    if existing is not None:
        return
    await repository.create_user(
        username=settings.ADMIN_USERNAME,
        password_hash=hash_password(settings.ADMIN_PASSWORD),
    )
    logger.info("Создан администратор %r", settings.ADMIN_USERNAME)


async def recompute_loop(repository: Repository, stop: asyncio.Event) -> None:
    interval = settings.RECOMPUTE_INTERVAL_SEC
    while not stop.is_set():
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
            return
        except asyncio.TimeoutError:
            pass

        if not state.realtime_enabled:
            continue
        try:
            await recompute(repository, reason="timer")
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            state.last_error = str(exc)
            logger.exception("Ошибка пересчёта по таймеру: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    repository = get_repository_or_none() or build_repository()
    set_repository(repository)

    state.realtime_enabled = settings.REALTIME_ENABLED

    await ensure_admin(repository)

    if settings.SEED_ON_STARTUP:
        await seed_if_empty(repository, settings.SEED_FILE)

    if settings.RECOMPUTE_ON_STARTUP:
        try:
            await recompute(repository, reason="startup")
        except Exception as exc:  # noqa: BLE001
            state.last_error = str(exc)
            logger.exception("Стартовый пересчёт не удался: %s", exc)

    stop = asyncio.Event()
    task: asyncio.Task | None = None
    if settings.REALTIME_ENABLED and settings.RECOMPUTE_INTERVAL_SEC > 0:
        task = asyncio.create_task(recompute_loop(repository, stop), name="recompute-loop")

    logger.info(
        "Сервис запущен: storage=%s, интервал пересчёта=%ss, данные от %s, OIDC=%s, metrics_token=%s",
        settings.STORAGE_BACKEND,
        settings.RECOMPUTE_INTERVAL_SEC,
        state.last_updated or "—",
        "вкл" if settings.oidc_enabled else "выкл",
        "да" if settings.METRICS_TOKEN else "нет",
    )

    try:
        yield
    finally:
        stop.set()
        if task is not None:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
        logger.info("Сервис остановлен в %s", utcnow().isoformat())


def metrics_guard(authorization: str | None = Header(default=None)) -> None:
    token = settings.METRICS_TOKEN
    if not token:
        return
    expected = f"Bearer {token}"
    if not authorization or not hmac.compare_digest(authorization, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Метрики защищены токеном",
            headers={"WWW-Authenticate": "Bearer"},
        )


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        docs_url=f"{settings.API_PREFIX}/docs",
        redoc_url=f"{settings.API_PREFIX}/redoc",
        openapi_url=f"{settings.API_PREFIX}/openapi.json",
        lifespan=lifespan,
    )

    if settings.RATE_LIMIT_ENABLED:
        limiter = RateLimiter(
            window=settings.RATE_LIMIT_WINDOW_SEC,
            api_limit=settings.RATE_LIMIT_API_REQUESTS,
            login_limit=settings.RATE_LIMIT_LOGIN_REQUESTS,
            max_clients=settings.RATE_LIMIT_MAX_CLIENTS,
        )
        app.state.rate_limiter = limiter
        app.add_middleware(RateLimitMiddleware, limiter=limiter, prefix=settings.API_PREFIX)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
        expose_headers=["Retry-After"],
    )

    if settings.oidc_enabled:
        from starlette.middleware.sessions import SessionMiddleware

        app.add_middleware(SessionMiddleware, secret_key=settings.JWT_SECRET, same_site="lax")

    @app.get(
        "/metrics",
        tags=["system"],
        summary="Метрики в формате Prometheus",
        dependencies=[Depends(metrics_guard)],
        response_class=Response,
        responses={200: {"content": {CONTENT_TYPE_LATEST: {}}}},
    )
    def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    prefix = settings.API_PREFIX
    rate_limit_responses = {
        429: {
            "model": RateLimitOut,
            "description": "Превышен лимит запросов с IP-адреса",
            "headers": {"Retry-After": {"schema": {"type": "integer"}, "description": "Ожидание, секунды"}},
        },
    }
    for route, suffix, tag in (
        (auth.router, "/auth", "auth"),
        (oidc.router, "/auth", "auth"),
        (customers.router, "/customers", "customers"),
        (analytics.router, "/analytics", "analytics"),
        (model_settings.router, "/model", "model"),
        (source.router, "/source", "source"),
        (events.router, "", "events"),
    ):
        app.include_router(route, prefix=prefix + suffix, tags=[tag], responses=rate_limit_responses)

    @app.get("/health", tags=["system"], summary="Проверка живости")
    async def health() -> dict:
        return {
            "status": "ok",
            "last_updated": state.last_updated.isoformat() if state.last_updated else None,
        }

    return app


app = create_app()
