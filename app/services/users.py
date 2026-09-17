"""User account services."""

from datetime import datetime, timezone

from sqlalchemy import func, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.errors import ConflictError, NotFoundError
from app.models import AuthSession, Doctor, User, UserRole
from app.schemas.user import UserCreate, UserUpdate
from app.services.auth import normalize_username
from app.services.security import hash_password


def get_user(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise NotFoundError("User")
    return user


def save_user(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise ConflictError("Username or doctor registration number already exists.") from error


def create_user(db: Session, data: UserCreate) -> User:
    user = User(username=normalize_username(data.username),
                password_hash=hash_password(data.password), role=data.role,
                is_active=data.is_active)
    if data.doctor is not None:
        user.doctor = Doctor(**data.doctor.model_dump())
    db.add(user)
    save_user(db)
    return user


def update_user(db: Session, user_id: int, data: UserUpdate) -> User:
    # Serialize account changes so concurrent requests cannot remove the last admin.
    db.execute(text("SELECT pg_advisory_xact_lock(724031, 1)"))
    doctor = db.scalar(select(Doctor).where(Doctor.user_id == user_id).with_for_update())
    user = get_user(db, user_id)
    db.refresh(user)
    role = data.role if data.role is not None else user.role
    active = data.is_active if data.is_active is not None else user.is_active
    if user.role == UserRole.ADMINISTRATOR and user.is_active and (
        role != UserRole.ADMINISTRATOR or not active
    ):
        others = db.scalar(select(func.count()).select_from(User).where(
            User.role == UserRole.ADMINISTRATOR, User.is_active.is_(True), User.id != user.id,
        ))
        if not others:
            raise ConflictError("The last active administrator cannot be disabled or demoted.")
    if data.doctor is not None and (role != UserRole.DOCTOR or doctor is not None):
        raise ConflictError("Supply a profile only when assigning the doctor role without an existing profile.")
    if role == UserRole.DOCTOR and doctor is None:
        if data.doctor is None:
            raise ConflictError("Assigning the doctor role requires a doctor profile.")
        user.doctor = Doctor(**data.doctor.model_dump())
    if doctor is not None and role != user.role:
        # Preserve historical appointment/visit references when changing roles.
        doctor.is_active = role == UserRole.DOCTOR
    if role != user.role or active != user.is_active:
        db.execute(update(AuthSession).where(
            AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None),
        ).values(revoked_at=datetime.now(timezone.utc)))
    user.role, user.is_active = role, active
    save_user(db)
    return user
