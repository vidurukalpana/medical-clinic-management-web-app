from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.errors import AuthenticationRequiredError, ForbiddenError
from app.models import (
    AuthSession,
    Availability,
    Doctor,
    DoctorUnavailability,
    User,
    UserRole,
)
from app.services.auth import get_active_auth_session
from app.services.doctor_scheduling import get_availability, get_unavailability
from app.services.doctors import get_doctor

bearer_scheme = HTTPBearer(auto_error=False)

DatabaseSession = Annotated[Session, Depends(get_db)]
BearerCredentials = Annotated[
    HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
]


def get_current_auth_session(
    credentials: BearerCredentials,
    db: DatabaseSession,
) -> AuthSession:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AuthenticationRequiredError()
    return get_active_auth_session(db, credentials.credentials)


CurrentAuthSession = Annotated[AuthSession, Depends(get_current_auth_session)]


def get_current_user(auth_session: CurrentAuthSession) -> User:
    return auth_session.user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_administrator(current_user: CurrentUser) -> User:
    if current_user.role != UserRole.ADMINISTRATOR:
        raise ForbiddenError("Administrator permission required.")
    return current_user


AdministratorUser = Annotated[User, Depends(require_administrator)]


def require_doctor(current_user: CurrentUser) -> Doctor:
    if current_user.role != UserRole.DOCTOR or current_user.doctor is None:
        raise ForbiddenError("Doctor permission required.")
    return current_user.doctor


CurrentDoctor = Annotated[Doctor, Depends(require_doctor)]


def get_schedule_doctor(
    doctor_id: int,
    _: CurrentUser,
    db: DatabaseSession,
) -> Doctor:
    return get_doctor(db, doctor_id)


ScheduleDoctor = Annotated[Doctor, Depends(get_schedule_doctor)]


def require_schedule_manager(
    doctor: ScheduleDoctor,
    current_user: CurrentUser,
) -> Doctor:
    if current_user.role == UserRole.ADMINISTRATOR:
        return doctor
    if current_user.role == UserRole.DOCTOR and doctor.user_id == current_user.id:
        return doctor
    raise ForbiddenError("You can manage only your own schedule.")


ScheduleManagerDoctor = Annotated[Doctor, Depends(require_schedule_manager)]


def get_schedule_availability(
    availability_id: int,
    doctor: ScheduleManagerDoctor,
    db: DatabaseSession,
) -> Availability:
    return get_availability(db, doctor.id, availability_id)


ScheduleAvailability = Annotated[
    Availability,
    Depends(get_schedule_availability),
]


def get_schedule_unavailability(
    unavailability_id: int,
    doctor: ScheduleManagerDoctor,
    db: DatabaseSession,
) -> DoctorUnavailability:
    return get_unavailability(db, doctor.id, unavailability_id)


ScheduleUnavailability = Annotated[
    DoctorUnavailability,
    Depends(get_schedule_unavailability),
]
