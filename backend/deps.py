"""FastAPI-зависимости: текущий пользователь и доступ к хранилищу."""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError

from backend.domain import User, utcnow
from backend.repository import Repository, get_repository
from backend.security import decode_token

#: ``auto_error=False`` — чтобы самим вернуть понятный 401 вместо 403.
bearer_scheme = HTTPBearer(auto_error=False)


def repo() -> Repository:
    return get_repository()


Repo = Annotated[Repository, Depends(repo)]


async def get_current_user(
    repository: Repo,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Требуется авторизация",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None or not credentials.credentials:
        raise unauthorized

    try:
        payload = decode_token(credentials.credentials)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Недействительный токен",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None

    jti = payload.get("jti")
    subject = payload.get("sub")
    if not jti or not subject:
        raise unauthorized

    session = await repository.get_session(jti)
    if session is None or session.is_expired(utcnow()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Сессия истекла, войдите заново",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id = int(subject)
    except (TypeError, ValueError):
        raise unauthorized from None

    user = await repository.get_user(user_id)
    if user is None:
        raise unauthorized
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
