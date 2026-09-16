from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.errors import BadRequestError, ConflictError, DoctorFullyBookedError, NotFoundError
from app.models import Appointment, Doctor, Visit
from app.schemas.visit import VisitUpdate
from app.services.patients import get_patient
from app.services.appointments import available_slots


def clinic_today(clinic_timezone: str) -> date:
    return datetime.now(ZoneInfo(clinic_timezone)).date()


def get_visit(db: Session, visit_id: int) -> Visit:
    visit = db.get(Visit, visit_id)
    if visit is None:
        raise NotFoundError("Visit")
    return visit


def list_queue(db: Session, doctor_id: int, day: date) -> list[Visit]:
    return list(db.scalars(
        select(Visit)
        .outerjoin(Visit.appointment)
        .options(joinedload(Visit.appointment))
        .where(Visit.doctor_id == doctor_id, Visit.visit_date == day)
        .order_by(Appointment.start_at.asc().nulls_last(), Visit.queue_number)
    ))


def create_visit(
    db: Session,
    doctor: Doctor,
    patient_id: int,
    day: date,
    presenting_complaint: str | None,
    appointment: Appointment | None = None,
) -> Visit:
    """Allocate a number while the caller holds the doctor's row lock."""
    if not doctor.is_active or not doctor.user.is_active:
        raise ConflictError("The doctor is inactive.")
    get_patient(db, patient_id)
    if appointment is not None:
        if appointment.status != "scheduled":
            raise ConflictError("Only scheduled appointments can be checked in.")
        if db.scalar(select(Visit.id).where(Visit.appointment_id == appointment.id)):
            raise ConflictError("This appointment has already been checked in.")
    if db.scalar(select(Visit.id).where(
        Visit.doctor_id == doctor.id,
        Visit.patient_id == patient_id,
        Visit.visit_date == day,
        Visit.status.in_(("waiting", "in_progress")),
    )):
        raise ConflictError("This patient is already in this doctor's queue today.")
    last_number = db.scalar(select(func.max(Visit.queue_number)).where(
        Visit.doctor_id == doctor.id, Visit.visit_date == day,
    )) or 0
    visit = Visit(
        appointment_id=appointment.id if appointment else None,
        doctor_id=doctor.id,
        patient_id=patient_id,
        visit_date=day,
        queue_number=last_number + 1,
        status="waiting",
        presenting_complaint=presenting_complaint,
    )
    db.add(visit)
    return visit


def create_walk_in(
    db: Session, doctor: Doctor, patient_id: int,
    presenting_complaint: str | None, clinic_timezone: str,
) -> Visit:
    """Reserve today's next free slot and queue the patient atomically."""
    day = clinic_today(clinic_timezone)
    visit = create_visit(db, doctor, patient_id, day, presenting_complaint)
    slots = available_slots(db, doctor, day, clinic_timezone)
    if not slots:
        raise DoctorFullyBookedError()
    slot = slots[0]
    visit.appointment = Appointment(
        doctor_id=doctor.id,
        patient_id=patient_id,
        start_at=slot.start_at,
        end_at=slot.end_at,
        reason="Walk-in",
        status="scheduled",
    )
    return visit


def check_in(
    db: Session, doctor: Doctor, appointment: Appointment,
    presenting_complaint: str | None, clinic_timezone: str,
) -> Visit:
    day = clinic_today(clinic_timezone)
    if appointment.start_at.astimezone(ZoneInfo(clinic_timezone)).date() != day:
        raise BadRequestError("Check-in is allowed only on the appointment's clinic date.")
    return create_visit(
        db, doctor, appointment.patient_id, day, presenting_complaint, appointment,
    )


def update_visit(db: Session, visit: Visit, data: VisitUpdate) -> Visit:
    if visit.status in ("completed", "cancelled"):
        raise ConflictError("Completed or cancelled visits cannot be edited.")
    transitions = {
        "waiting": {"waiting", "in_progress", "cancelled"},
        "in_progress": {"in_progress", "completed", "cancelled"},
    }
    if data.status is not None and data.status not in transitions[visit.status]:
        raise ConflictError("Invalid consultation status transition.")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(visit, field, value)
    if visit.appointment_id is not None and data.status in ("completed", "cancelled"):
        appointment = db.get(Appointment, visit.appointment_id)
        appointment.status = data.status
    return visit
