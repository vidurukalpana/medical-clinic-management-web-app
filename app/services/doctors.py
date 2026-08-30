from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Doctor
from app.schemas.doctor import DoctorAdminUpdate, DoctorSelfUpdate


class DuplicateRegistrationNumberError(Exception):
    pass


def list_doctors(db: Session, include_inactive: bool = False) -> list[Doctor]:
    statement = select(Doctor).order_by(Doctor.id)
    if not include_inactive:
        statement = statement.where(Doctor.is_active.is_(True))
    return list(db.scalars(statement))


def get_doctor(db: Session, doctor_id: int) -> Doctor | None:
    return db.get(Doctor, doctor_id)


def update_doctor(
    db: Session,
    doctor: Doctor,
    update: DoctorSelfUpdate | DoctorAdminUpdate,
) -> Doctor:
    for field_name, value in update.model_dump(exclude_unset=True).items():
        setattr(doctor, field_name, value)

    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise DuplicateRegistrationNumberError from error

    db.refresh(doctor)
    return doctor
