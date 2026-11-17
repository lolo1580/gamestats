from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta
from typing import Annotated

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from fastapi import Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from config import get_settings
from database import get_db
from models import AuthSession, User, utcnow
from utils import ensure_utc

COOKIE_NAME = "gamestats_session"
SESSION_DAYS = get_settings().session_days
COOKIE_SECURE = get_settings().cookie_secure

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError, ValueError):
        return False


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_auth_session(db: Session, user: User, request: Request) -> str:
    token = secrets.token_urlsafe(48)
    db.add(
        AuthSession(
            token_hash=_hash_token(token),
            user_id=user.id,
            expires_at=utcnow() + timedelta(days=SESSION_DAYS),
            user_agent=(request.headers.get("user-agent") or "")[:255],
        )
    )
    db.commit()
    return token


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=SESSION_DAYS * 24 * 3600,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(key=COOKIE_NAME, path="/", samesite="lax", secure=COOKIE_SECURE)


def delete_auth_session(db: Session, token: str | None) -> None:
    if not token:
        return
    session = db.scalar(
        select(AuthSession).where(AuthSession.token_hash == _hash_token(token))
    )
    if session is not None:
        db.delete(session)
        db.commit()


def delete_user_sessions(db: Session, user_id: int) -> None:
    for session in db.scalars(
        select(AuthSession).where(AuthSession.user_id == user_id)
    ).all():
        db.delete(session)
    db.commit()


def user_from_token(db: Session, token: str | None) -> User | None:
    if not token:
        return None

    session = db.scalar(
        select(AuthSession).where(AuthSession.token_hash == _hash_token(token))
    )
    if session is None:
        return None

    expires_at = ensure_utc(session.expires_at)
    if expires_at is None or expires_at <= utcnow():
        db.delete(session)
        db.commit()
        return None

    user = session.user
    if user is None or not user.is_active:
        return None
    return user


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    user = user_from_token(db, request.cookies.get(COOKIE_NAME))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentification requise.",
        )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_admin(user: CurrentUser) -> User:
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Droits administrateur requis.",
        )
    return user


AdminUser = Annotated[User, Depends(require_admin)]
