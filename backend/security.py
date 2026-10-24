"""Пароли и JWT."""
from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

from jose import jwt
from passlib.context import CryptContext

from backend.config import settings
from backend.domain import utcnow

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return pwd_context.verify(password, password_hash)
    except ValueError:
        # Повреждённый хеш в хранилище — это неверный пароль, а не 500.
        return False


def create_token(user_id: int, jti: str) -> str:
    expire = utcnow() + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "jti": jti, "exp": expire}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """Разбор токена. Бросает ``JWTError`` при любой проблеме."""
    return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])


def new_jti() -> str:
    return uuid4().hex
