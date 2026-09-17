from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.errors import ConflictError, DuplicateRegistrationNumberError, NotFoundError
from app.models import Doctor, User, UserRole
from app.schemas.doctor import DoctorAdminUpdate, DoctorSelfUpdate


def list_doctors(db: Session) -> list[Doctor]:
    statement = select(Doctor).join(User).where(
        Doctor.is_active.is_(True), User.is_active.is_(True),
    ).order_by(Doctor.id)
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
    db.execute(select(Doctor.id).where(Doctor.id == doctor.id).with_for_update())
    db.refresh(doctor)
    db.refresh(doctor.user)
    if getattr(update, "is_active", None) is True and doctor.user.role != UserRole.DOCTOR:
        raise ConflictError("Assign the doctor account role before activating its profile.")
    for field_name, value in update.model_dump(exclude_unset=True).items():
        setattr(doctor, field_name, value)

    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise DuplicateRegistrationNumberError() from error

    db.refresh(doctor)
    return doctor
