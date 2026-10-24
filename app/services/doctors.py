from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.errors import ConflictError, DuplicateRegistrationNumberError, NotFoundError
from app.models import Doctor, User, UserRole
from app.schemas.doctor import PROFILE_FIELDS, DoctorAdminUpdate, DoctorPublicRead, DoctorSelfUpdate, WeeklySession


def list_doctors(db: Session) -> list[Doctor]:
    statement = select(Doctor).join(User).where(
        Doctor.is_active.is_(True), User.is_active.is_(True),
    ).options(selectinload(Doctor.availability)).order_by(Doctor.id)
    return list(db.scalars(statement))


def public_profile(doctor: Doctor) -> DoctorPublicRead:
    """The patient-facing profile, with the doctor's active weekly sessions."""
    sessions = sorted(
        (item for item in doctor.availability if item.is_active),
        key=lambda item: (item.weekday, item.start_time),
    )
    return DoctorPublicRead(
        id=doctor.id, display_name=doctor.display_name,
        registration_number=doctor.registration_number,
        **{field: getattr(doctor, field) for field in PROFILE_FIELDS},
        weekly_sessions=[WeeklySession(weekday=item.weekday, start_time=item.start_time,
                                       end_time=item.end_time) for item in sessions],
    )


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
