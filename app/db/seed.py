from dataclasses import dataclass

from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import Doctor, User, UserRole
from app.services.auth import normalize_username
from app.services.security import hash_password


@dataclass(frozen=True)
class InitialDoctor:
    username: str
    password: str | None
    password_setting_name: str
    display_name: str
    registration_number: str


def seed_initial_accounts(db: Session, settings: Settings) -> None:
    """Create the local administrator and two doctor accounts when missing."""
    _create_user_if_missing(
        db=db,
        username=settings.admin_username,
        password=_read_secret(settings.admin_password),
        password_setting_name="CLINIC_ADMIN_PASSWORD",
        role=UserRole.ADMINISTRATOR,
    )

    initial_doctors = (
        InitialDoctor(
            username=settings.doctor_one_username,
            password=_read_secret(settings.doctor_one_password),
            password_setting_name="CLINIC_DOCTOR_ONE_PASSWORD",
            display_name="Doctor One",
            registration_number="DOC-001",
        ),
        InitialDoctor(
            username=settings.doctor_two_username,
            password=_read_secret(settings.doctor_two_password),
            password_setting_name="CLINIC_DOCTOR_TWO_PASSWORD",
            display_name="Doctor Two",
            registration_number="DOC-002",
        ),
    )

    for initial_doctor in initial_doctors:
        user = _create_user_if_missing(
            db=db,
            username=initial_doctor.username,
            password=initial_doctor.password,
            password_setting_name=initial_doctor.password_setting_name,
            role=UserRole.DOCTOR,
        )
        _create_doctor_if_missing(db, user, initial_doctor)

    db.commit()


def _create_user_if_missing(
    db: Session,
    username: str,
    password: str | None,
    password_setting_name: str,
    role: UserRole,
) -> User:
    normalized_username = normalize_username(username)
    user = db.scalar(select(User).where(User.username == normalized_username))
    if user is not None:
        if user.role != role:
            raise RuntimeError(
                f"Initial username '{normalized_username}' already has another role."
            )
        return user

    if not password:
        raise RuntimeError(
            f"{password_setting_name} must be set before creating "
            f"the initial '{normalized_username}' account."
        )

    user = User(
        username=normalized_username,
        password_hash=hash_password(password),
        role=role,
    )
    db.add(user)
    db.flush()
    return user


def _create_doctor_if_missing(
    db: Session, user: User, initial_doctor: InitialDoctor
) -> Doctor:
    doctor = db.scalar(select(Doctor).where(Doctor.user_id == user.id))
    if doctor is not None:
        return doctor

    registration_owner = db.scalar(
        select(Doctor).where(
            Doctor.registration_number == initial_doctor.registration_number
        )
    )
    if registration_owner is not None:
        raise RuntimeError(
            "Initial doctor registration number "
            f"'{initial_doctor.registration_number}' already exists."
        )

    doctor = Doctor(
        user_id=user.id,
        display_name=initial_doctor.display_name,
        registration_number=initial_doctor.registration_number,
    )
    db.add(doctor)
    return doctor


def _read_secret(secret: SecretStr | None) -> str | None:
    if secret is None:
        return None
    return secret.get_secret_value()
