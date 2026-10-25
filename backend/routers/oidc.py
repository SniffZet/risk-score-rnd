from __future__ import annotations

import logging
import secrets
from datetime import timedelta

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import RedirectResponse

from backend.config import settings
from backend.deps import Repo
from backend.domain import Session, utcnow
from backend.security import create_token, hash_password, new_jti

router = APIRouter()
logger = logging.getLogger(__name__)

_oauth = None


def _client():
    global _oauth
    if _oauth is None:
        from authlib.integrations.starlette_client import OAuth

        _oauth = OAuth()
        issuer = settings.OIDC_ISSUER.rstrip("/")
        _oauth.register(
            name="oidc",
            client_id=settings.OIDC_CLIENT_ID,
            client_secret=settings.OIDC_CLIENT_SECRET or None,
            server_metadata_url=f"{issuer}/.well-known/openid-configuration",
            client_kwargs={"scope": settings.OIDC_SCOPES},
        )
    return _oauth.create_client("oidc")


def _require_enabled() -> None:
    if not settings.oidc_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="OIDC не настроен")


def _redirect_url(request: Request) -> str:
    if settings.OIDC_REDIRECT_URL:
        return settings.OIDC_REDIRECT_URL
    return str(request.url_for("oidc_callback"))


@router.get("/oidc/login", name="oidc_login", summary="Начать вход через OIDC")
async def oidc_login(request: Request):
    _require_enabled()
    return await _client().authorize_redirect(request, _redirect_url(request))


@router.get("/oidc/callback", name="oidc_callback", summary="Возврат от OIDC-провайдера")
async def oidc_callback(request: Request, repository: Repo):
    _require_enabled()
    client = _client()
    try:
        token = await client.authorize_access_token(request)
    except Exception as exc:  # noqa: BLE001
        logger.warning("OIDC: провайдер не подтвердил вход: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="SSO: провайдер не подтвердил вход"
        ) from exc

    userinfo = token.get("userinfo") or await client.userinfo(token=token)
    username = userinfo.get("preferred_username") or userinfo.get("email") or userinfo.get("sub")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="SSO: провайдер не вернул имя пользователя"
        )

    user = await repository.get_user_by_username(username)
    if user is None:
        user = await repository.create_user(
            username=username, password_hash=hash_password(secrets.token_urlsafe(32))
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
    access = create_token(user.id, jti)
    return RedirectResponse(url=f"{settings.FRONTEND_URL}#token={access}", status_code=302)
