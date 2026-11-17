from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from database import get_db
from models import User
from routes_auth import normalize_email, normalize_username
from schemas import UserCreateIn, UserOut, UserUpdateIn
from security import AdminUser, delete_user_sessions, hash_password

router = APIRouter(prefix="/api/users", tags=["users"])


def _active_admin_count(db: Session) -> int:
    return int(
        db.scalar(
            select(func.count(User.id)).where(
                User.role == "admin", User.is_active.is_(True)
            )
        )
        or 0
    )


def _ensure_email_available(
    db: Session, email: str | None, exclude_user_id: int | None = None
) -> None:
    if not email:
        return
    query = select(User).where(User.email == email)
    if exclude_user_id is not None:
        query = query.where(User.id != exclude_user_id)
    if db.scalar(query) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cette adresse email est déjà utilisée.",
        )


@router.get("", response_model=list[UserOut])
def list_users(_admin: AdminUser, db: Session = Depends(get_db)) -> list[User]:
    return list(db.scalars(select(User).order_by(User.username)).all())


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreateIn,
    _admin: AdminUser,
    db: Session = Depends(get_db),
) -> User:
    username = normalize_username(payload.username)
    email = normalize_email(payload.email)

    if db.scalar(select(User).where(User.username == username)) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ce nom d'utilisateur existe déjà.",
        )
    _ensure_email_available(db, email)

    user = User(
        username=username,
        email=email,
        password_hash=hash_password(payload.password),
        role=payload.role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    payload: UserUpdateIn,
    admin: AdminUser,
    db: Session = Depends(get_db),
) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable.")

    fields = payload.model_fields_set

    if "email" in fields:
        email = normalize_email(payload.email)
        _ensure_email_available(db, email, exclude_user_id=user.id)
        user.email = email

    new_role = user.role
    if "role" in fields and payload.role is not None:
        new_role = payload.role

    new_active = user.is_active
    if "is_active" in fields and payload.is_active is not None:
        new_active = payload.is_active

    if user.id == admin.id and new_role != "admin":
        raise HTTPException(
            status_code=400,
            detail="Vous ne pouvez pas retirer vos propres droits administrateur.",
        )
    if user.id == admin.id and not new_active:
        raise HTTPException(
            status_code=400,
            detail="Vous ne pouvez pas désactiver votre propre compte.",
        )
    if user.role == "admin" and user.is_active and (
        new_role != "admin" or not new_active
    ):
        if _active_admin_count(db) <= 1:
            raise HTTPException(
                status_code=400,
                detail="Le dernier administrateur actif ne peut pas être modifié.",
            )

    user.role = new_role
    user.is_active = new_active

    if "password" in fields and payload.password:
        user.password_hash = hash_password(payload.password)
        db.commit()
        delete_user_sessions(db, user.id)
    else:
        db.commit()

    db.refresh(user)
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    admin: AdminUser,
    db: Session = Depends(get_db),
) -> None:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable.")
    if user.id == admin.id:
        raise HTTPException(
            status_code=400, detail="Vous ne pouvez pas supprimer votre propre compte."
        )
    if user.role == "admin" and user.is_active and _active_admin_count(db) <= 1:
        raise HTTPException(
            status_code=400,
            detail="Le dernier administrateur actif ne peut pas être supprimé.",
        )

    db.delete(user)
    db.commit()
