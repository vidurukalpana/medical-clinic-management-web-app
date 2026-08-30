from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session, selectinload

from app.models import AuthSession, User, UserRole
from app.services.security import (
    DUMMY_PASSWORD_HASH,
    create_session_token,
    hash_password,
    hash_session_token,
    verify_password,
)


class InvalidCurrentPasswordError(Exception):
    pass


def normalize_username(username: str) -> str:
    return username.strip().lower()


def authenticate_user(db: Session, username: str, password: str) -> User | None:
    user = db.scalar(
        select(User)
        .options(selectinload(User.doctor))
        .where(User.username == normalize_username(username))
    )

    if user is None:
        verify_password(password, DUMMY_PASSWORD_HASH)
        return None

    if not verify_password(password, user.password_hash) or not user.is_active:
        return None

    if user.role == UserRole.DOCTOR and (
        user.doctor is None or not user.doctor.is_active
    ):
        return None

    return user


def create_auth_session(
    db: Session, user: User, expires_in_hours: int
) -> tuple[str, AuthSession]:
    now = datetime.now(timezone.utc)
    db.execute(
        delete(AuthSession).where(
            AuthSession.user_id == user.id,
            AuthSession.expires_at <= now,
        )
    )

    token = create_session_token()
    auth_session = AuthSession(
        user_id=user.id,
        token_hash=hash_session_token(token),
        expires_at=now + timedelta(hours=expires_in_hours),
    )
    db.add(auth_session)
    db.commit()
    db.refresh(auth_session)
    return token, auth_session


def revoke_auth_session(db: Session, auth_session: AuthSession) -> None:
    auth_session.revoked_at = datetime.now(timezone.utc)
    db.commit()


def change_user_password(
    db: Session,
    user: User,
    current_password: str,
    new_password: str,
) -> None:
    if not verify_password(current_password, user.password_hash):
        raise InvalidCurrentPasswordError
    set_user_password(db, user, new_password)


def set_user_password(db: Session, user: User, new_password: str) -> None:
    revoked_at = datetime.now(timezone.utc)
    user.password_hash = hash_password(new_password)
    db.execute(
        update(AuthSession)
        .where(
            AuthSession.user_id == user.id,
            AuthSession.revoked_at.is_(None),
        )
        .values(revoked_at=revoked_at)
    )
    db.commit()
