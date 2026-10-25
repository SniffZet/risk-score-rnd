from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    APP_NAME: str = "Churn Risk Analyzer"
    APP_VERSION: str = "1.1.0"
    API_PREFIX: str = "/api/v1"

    STORAGE_BACKEND: str = "file"
    DATA_DIR: str = "var"

    JWT_SECRET: str = "change-me"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 480
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "admin"

    OIDC_ISSUER: str = ""
    OIDC_CLIENT_ID: str = ""
    OIDC_CLIENT_SECRET: str = ""
    OIDC_SCOPES: str = "openid email profile"
    OIDC_PROVIDER_NAME: str = "SSO"
    OIDC_REDIRECT_URL: str = ""
    FRONTEND_URL: str = "/"

    METRICS_TOKEN: str = ""

    RECOMPUTE_INTERVAL_SEC: int = 60
    RECOMPUTE_ON_STARTUP: bool = True
    REALTIME_ENABLED: bool = True

    SEED_FILE: str = "data/data.json"
    SEED_ON_STARTUP: bool = True

    MAX_UPLOAD_BYTES: int = 50 * 1024 * 1024
    JOURNAL_MAX_EVENTS: int = 50_000

    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    SSE_QUEUE_SIZE: int = 100
    SSE_HEARTBEAT_SEC: int = 15

    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_WINDOW_SEC: int = Field(default=60, ge=1)
    RATE_LIMIT_API_REQUESTS: int = Field(default=300, ge=1)
    RATE_LIMIT_LOGIN_REQUESTS: int = Field(default=5, ge=1)
    RATE_LIMIT_MAX_CLIENTS: int = Field(default=10_000, ge=1)

    @property
    def oidc_enabled(self) -> bool:
        return bool(self.OIDC_ISSUER and self.OIDC_CLIENT_ID)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
