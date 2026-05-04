from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, Header, HTTPException, Request, Response
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from .config import get_settings
from .db import get_db
from .models import User


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def create_session_token(user_id: str) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=settings.session_ttl_seconds)).timestamp()),
    }
    return jwt.encode(payload, settings.session_secret, algorithm="HS256")


def decode_session_token(token: str) -> Optional[str]:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.session_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    sub = payload.get("sub")
    return str(sub) if sub else None


def _cookie_kwargs() -> dict:
    settings = get_settings()
    return {
        "path": "/",
        "secure": settings.cookie_secure,
        "samesite": settings.cookie_samesite,
    }


def ensure_csrf_cookie(request: Request, response: Response) -> str:
    settings = get_settings()
    existing = request.cookies.get(settings.csrf_cookie_name)
    if existing:
        return existing
    token = secrets.token_urlsafe(32)
    response.set_cookie(
        settings.csrf_cookie_name,
        token,
        httponly=False,
        max_age=settings.session_ttl_seconds,
        **_cookie_kwargs(),
    )
    return token


def set_session_cookie(response: Response, user_id: str) -> None:
    settings = get_settings()
    response.set_cookie(
        settings.session_cookie_name,
        create_session_token(user_id),
        httponly=True,
        max_age=settings.session_ttl_seconds,
        **_cookie_kwargs(),
    )


def clear_session_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(settings.session_cookie_name, path="/")


def verify_csrf(
    request: Request,
    x_csrf_token: Optional[str] = Header(default=None, alias="X-CSRF-Token"),
) -> str:
    settings = get_settings()
    cookie_token = request.cookies.get(settings.csrf_cookie_name)
    if not cookie_token or not x_csrf_token or cookie_token != x_csrf_token:
        raise HTTPException(status_code=403, detail="CSRF token missing or invalid")
    return cookie_token


def get_optional_user(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    settings = get_settings()
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        return None
    user_id = decode_session_token(token)
    if not user_id:
        return None
    return db.get(User, user_id)


def get_current_user(user: Optional[User] = Depends(get_optional_user)) -> User:
    if not user:
        raise HTTPException(status_code=401, detail="authentication required")
    return user
