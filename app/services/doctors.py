from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.errors import DuplicateRegistrationNumberError, NotFoundError
from app.models import Doctor, User, UserRole
from app.schemas.doctor import DoctorAdminUpdate, DoctorSelfUpdate


def list_doctors(db: Session, current_user: User) -> list[Doctor]:
    statement = select(Doctor).order_by(Doctor.id)
    if current_user.role != UserRole.ADMINISTRATOR:
        statement = statement.where(Doctor.is_active.is_(True))
    return list(db.scalars(statement))


def get_doctor(db: Session, doctor_id: int) -> Doctor:
    doctor = db.get(Doctor, doctor_id)
    if doctor is None:
        raise NotFoundError("Doctor")
    return doctor


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
        raise DuplicateRegistrationNumberError() from error

    db.refresh(doctor)
    return doctor
