from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.db.session import get_db
from app.models import AuthSession, Doctor, User, UserRole
from app.services.security import hash_session_token

bearer_scheme = HTTPBearer(auto_error=False)

DatabaseSession = Annotated[Session, Depends(get_db)]
BearerCredentials = Annotated[
    HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
]


def authentication_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_auth_session(
    credentials: BearerCredentials,
    db: DatabaseSession,
) -> AuthSession:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise authentication_error()

    auth_session = db.scalar(
        select(AuthSession)
        .options(joinedload(AuthSession.user).joinedload(User.doctor))
        .where(
            AuthSession.token_hash == hash_session_token(credentials.credentials),
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > datetime.now(timezone.utc),
        )
    )
    if auth_session is None or not auth_session.user.is_active:
        raise authentication_error()

    user = auth_session.user
    if user.role == UserRole.DOCTOR and (
        user.doctor is None or not user.doctor.is_active
    ):
        raise authentication_error()

    return auth_session


CurrentAuthSession = Annotated[AuthSession, Depends(get_current_auth_session)]


def get_current_user(auth_session: CurrentAuthSession) -> User:
    return auth_session.user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_administrator(current_user: CurrentUser) -> User:
    if current_user.role != UserRole.ADMINISTRATOR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator permission required.",
        )
    return current_user


AdministratorUser = Annotated[User, Depends(require_administrator)]


def require_doctor(current_user: CurrentUser) -> Doctor:
    if current_user.role != UserRole.DOCTOR or current_user.doctor is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Doctor permission required.",
        )
    return current_user.doctor


CurrentDoctor = Annotated[Doctor, Depends(require_doctor)]
