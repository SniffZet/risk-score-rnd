"""Настройки приложения (не модели!).

Параметры самой модели риска — веса, пороги, горизонт — живут в
``backend.risk.defaults`` и меняются через API ``/model/settings``. Здесь только
инфраструктура: порт, секреты, путь к данным, лимиты.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    APP_NAME: str = "Churn Risk Analyzer"
    APP_VERSION: str = "1.0.0"
    API_PREFIX: str = "/api/v1"

    # --- хранилище ---------------------------------------------------------
    # "memory" — реализация в памяти. SQL-репозиторий добавляет человек,
    # который владеет схемой БД (data/001_schema.up.sql).
    STORAGE_BACKEND: str = "memory"

    # --- авторизация -------------------------------------------------------
    JWT_SECRET: str = "change-me"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 480
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "admin"

    # --- пересчёт ----------------------------------------------------------
    RECOMPUTE_INTERVAL_SEC: int = 60
    RECOMPUTE_ON_STARTUP: bool = True
    REALTIME_ENABLED: bool = True

    # --- первичная загрузка данных ----------------------------------------
    SEED_FILE: str = "data/data.json"
    SEED_ON_STARTUP: bool = True

    # --- лимиты ------------------------------------------------------------
    MAX_UPLOAD_BYTES: int = 50 * 1024 * 1024

    # --- CORS --------------------------------------------------------------
    # Никогда не используем ["*"] вместе с allow_credentials.
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # --- SSE ---------------------------------------------------------------
    SSE_QUEUE_SIZE: int = 100
    SSE_HEARTBEAT_SEC: int = 15


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
