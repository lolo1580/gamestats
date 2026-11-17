from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from database import get_db
from models import User, utcnow
from schemas import (
    AuthStatusOut,
    LoginIn,
    PasswordChangeIn,
    ProfileUpdateIn,
    SetupIn,
    UserOut,
)
from security import (
    COOKIE_NAME,
    CurrentUser,
    clear_session_cookie,
    create_auth_session,
    delete_auth_session,
    delete_user_sessions,
    hash_password,
    set_session_cookie,
    user_from_token,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

USERNAME_RE = re.compile(r"^[a-z0-9_.-]{3,64}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_username(value: str) -> str:
    username = value.strip().lower()
    if not USERNAME_RE.fullmatch(username):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Le nom d'utilisateur doit contenir 3 à 64 caractères (a-z, 0-9, ., _, -).",
        )
    return username


def normalize_email(value: str | None) -> str | None:
    if value is None:
        return None
    email = value.strip().lower()
    if not email:
        return None
    if len(email) > 255 or not EMAIL_RE.fullmatch(email):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Adresse email invalide.",
        )
    return email


def issue_session(
    db: Session, user: User, request: Request, response: Response
) -> str:
    token = create_auth_session(db, user, request)
    set_session_cookie(response, token)
    return token


@router.get("/status", response_model=AuthStatusOut)
def auth_status(
    request: Request,
    db: Session = Depends(get_db),
) -> AuthStatusOut:
    needs_setup = (db.scalar(select(func.count(User.id))) or 0) == 0
    user = user_from_token(db, request.cookies.get(COOKIE_NAME))
    return AuthStatusOut(
        needs_setup=needs_setup,
        authenticated=user is not None,
        user=UserOut.model_validate(user) if user else None,
    )


@router.post("/setup", response_model=UserOut)
def setup(
    payload: SetupIn,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> User:
    if (db.scalar(select(func.count(User.id))) or 0) > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="L'installation initiale est déjà terminée.",
        )

    user = User(
        username=normalize_username(payload.username),
        email=normalize_email(payload.email),
        password_hash=hash_password(payload.password),
        role="admin",
        is_active=True,
        last_login_at=utcnow(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    issue_session(db, user, request, response)
    return user


@router.post("/login", response_model=UserOut)
def login(
    payload: LoginIn,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> User:
    identifier = payload.identifier.strip().lower()
    user = db.scalar(
        select(User).where(
            or_(User.username == identifier, User.email == identifier)
        )
    )
    if user is None or not user.is_active or not verify_password(
        payload.password, user.password_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identifiant ou mot de passe incorrect.",
        )

    user.last_login_at = utcnow()
    db.commit()
    db.refresh(user)
    issue_session(db, user, request, response)
    return user


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> dict:
    delete_auth_session(db, request.cookies.get(COOKIE_NAME))
    clear_session_cookie(response)
    return {"ok": True}


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser) -> User:
    return user


@router.patch("/me", response_model=UserOut)
def update_me(
    payload: ProfileUpdateIn,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> User:
    if payload.locale is not None:
        user.locale = payload.locale
        db.commit()
        db.refresh(user)
    return user


@router.post("/password")
def change_password(
    payload: PasswordChangeIn,
    request: Request,
    response: Response,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> dict:
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mot de passe actuel incorrect.",
        )
    if payload.current_password == payload.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Le nouveau mot de passe doit être différent de l'ancien.",
        )

    user.password_hash = hash_password(payload.new_password)
    db.commit()
    delete_user_sessions(db, user.id)
    issue_session(db, user, request, response)
    return {"ok": True}
