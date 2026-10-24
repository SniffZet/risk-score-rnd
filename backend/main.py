"""Точка входа FastAPI-приложения."""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app

from backend.config import settings
from backend.domain import utcnow
from backend.repository import (
    MemoryRepository,
    Repository,
    get_repository_or_none,
    set_repository,
)
from backend.routers import analytics, auth, customers, events, model_settings, source
from backend.security import hash_password
from backend.services.recompute import recompute
from backend.services.seed import seed_if_empty
from backend.services.sse import subscriber_count
from backend.state import state

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)
logger = logging.getLogger("churn")


def build_repository() -> Repository:
    """Создать хранилище.

    Когда человек со стороны модели добавит SQL-реализацию
    (``app/repository_sql.py`` по схеме ``data/001_schema.up.sql``), здесь
    появится выбор по ``settings.STORAGE_BACKEND`` — остальной код не
    изменится.
    """
    if settings.STORAGE_BACKEND != "memory":
        raise RuntimeError(
            f"STORAGE_BACKEND={settings.STORAGE_BACKEND!r} ещё не поддерживается: "
            "SQL-реализацию добавляет человек со стороны модели"
        )
    return MemoryRepository()


async def ensure_admin(repository: Repository) -> None:
    """Создать администратора, если его нет. Повторный старт безопасен."""
    existing = await repository.get_user_by_username(settings.ADMIN_USERNAME)
    if existing is not None:
        return
    await repository.create_user(
        username=settings.ADMIN_USERNAME,
        password_hash=hash_password(settings.ADMIN_PASSWORD),
    )
    logger.info("Создан администратор %r", settings.ADMIN_USERNAME)


async def recompute_loop(repository: Repository, stop: asyncio.Event) -> None:
    """Периодический пересчёт.

    Ошибка внутри одной итерации не должна убивать задачу — иначе сервис
    молча перестанет обновлять данные до перезапуска.
    """
    interval = settings.RECOMPUTE_INTERVAL_SEC
    while not stop.is_set():
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
            return  # stop выставлен — выходим
        except asyncio.TimeoutError:
            pass

        if not state.realtime_enabled:
            continue
        try:
            await recompute(repository)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - задача обязана выжить
            state.last_error = str(exc)
            logger.exception("Ошибка пересчёта по таймеру: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Если хранилище уже подставлено (тесты, встраивание) — используем его.
    repository = get_repository_or_none() or build_repository()
    set_repository(repository)

    state.realtime_enabled = settings.REALTIME_ENABLED

    await ensure_admin(repository)

    if settings.SEED_ON_STARTUP:
        await seed_if_empty(repository, settings.SEED_FILE)

    if settings.RECOMPUTE_ON_STARTUP:
        try:
            await recompute(repository)
        except Exception as exc:  # noqa: BLE001 - сервис должен подняться
            state.last_error = str(exc)
            logger.exception("Стартовый пересчёт не удался: %s", exc)

    stop = asyncio.Event()
    task: asyncio.Task | None = None
    if settings.REALTIME_ENABLED and settings.RECOMPUTE_INTERVAL_SEC > 0:
        task = asyncio.create_task(recompute_loop(repository, stop), name="recompute-loop")

    logger.info(
        "Сервис запущен: storage=%s, интервал пересчёта=%ss, данные от %s",
        settings.STORAGE_BACKEND,
        settings.RECOMPUTE_INTERVAL_SEC,
        state.last_updated or "—",
    )

    try:
        yield
    finally:
        stop.set()
        if task is not None:
            task.cancel()
            # Дожидаемся завершения, иначе получим "Task was destroyed but it
            # is pending" и потеряем хвост лога.
            try:
                await task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
        logger.info("Сервис остановлен в %s", utcnow().isoformat())


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        docs_url=f"{settings.API_PREFIX}/docs",
        redoc_url=f"{settings.API_PREFIX}/redoc",
        openapi_url=f"{settings.API_PREFIX}/openapi.json",
        lifespan=lifespan,
    )

    # allow_origins=["*"] вместе с allow_credentials — недопустимая комбинация,
    # поэтому список источников задаётся настройкой.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

    app.mount("/metrics", make_asgi_app())

    prefix = settings.API_PREFIX
    app.include_router(auth.router, prefix=f"{prefix}/auth", tags=["auth"])
    app.include_router(customers.router, prefix=f"{prefix}/customers", tags=["customers"])
    app.include_router(analytics.router, prefix=f"{prefix}/analytics", tags=["analytics"])
    app.include_router(model_settings.router, prefix=f"{prefix}/model", tags=["model"])
    app.include_router(source.router, prefix=f"{prefix}/source", tags=["source"])
    app.include_router(events.router, prefix=prefix, tags=["events"])

    @app.get("/health", tags=["system"], summary="Проверка живости")
    async def health() -> dict:
        summary = state.summary
        return {
            "status": "ok",
            "storage": settings.STORAGE_BACKEND,
            "last_updated": state.last_updated.isoformat() if state.last_updated else None,
            "last_error": state.last_error,
            "recompute_count": state.recompute_count,
            "sse_subscribers": subscriber_count(),
            "customers_total": summary.customersTotal if summary else None,
            "reference_time": summary.referenceTime.isoformat() if summary else None,
        }

    return app


app = create_app()
