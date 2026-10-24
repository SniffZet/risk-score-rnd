"""Авторизация: вход, текущий пользователь, выход."""
from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials

from backend.config import settings
from backend.deps import CurrentUser, Repo, bearer_scheme
from backend.domain import Session, utcnow
from backend.schemas import LoginIn, TokenOut, UserOut
from backend.security import create_token, decode_token, new_jti, verify_password

router = APIRouter()


@router.post("/login", response_model=TokenOut, summary="Вход по логину и паролю")
async def login(payload: LoginIn, repository: Repo) -> TokenOut:
    user = await repository.get_user_by_username(payload.username)
    if user is None or not verify_password(payload.password, user.password_hash):
        # Одинаковый текст для «нет пользователя» и «неверный пароль»,
        # чтобы не подсказывать, какие логины существуют.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный логин или пароль",
        )

    jti = new_jti()
    now = utcnow()
    await repository.create_session(
        Session(
            id=jti,
            user_id=user.id,
            created_at=now,
            expires_at=now + timedelta(minutes=settings.JWT_EXPIRE_MINUTES),
        )
    )
    return TokenOut(access_token=create_token(user.id, jti))


@router.get("/me", response_model=UserOut, summary="Текущий пользователь")
async def me(user: CurrentUser) -> UserOut:
    return UserOut(id=user.id, username=user.username)


@router.post("/logout", summary="Выход (отзыв токена)")
async def logout(
    repository: Repo,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict[str, str]:
    # Выход идемпотентен: без токена или с мусорным токеном всё равно "ok",
    # но сессию удаляем только если токен действительно разобрался.
    if credentials and credentials.credentials:
        try:
            jti = decode_token(credentials.credentials).get("jti")
        except Exception:
            jti = None
        if jti:
            await repository.delete_session(jti)
    return {"status": "ok"}
