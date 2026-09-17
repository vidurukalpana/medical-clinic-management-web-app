from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.errors import BadRequestError, ConflictError, ForbiddenError, NotFoundError
from app.models import Appointment, Availability, Doctor, DoctorUnavailability, User, UserRole, Visit
from app.schemas.appointment import AppointmentCreate, AppointmentPage, AppointmentRead, AvailableSlot
from app.services.patients import get_patient


def get_booking_doctor(db: Session, doctor_id: int, *, lock: bool = False) -> Doctor:
    statement = select(Doctor).where(Doctor.id == doctor_id)
    if lock:
        statement = statement.with_for_update()
    doctor = db.scalar(statement)
    if doctor is None:
        raise NotFoundError("Doctor")
    return doctor


def available_slots(
    db: Session, doctor: Doctor, day: date, clinic_timezone: str,
    exclude_id: int | None = None,
) -> list[AvailableSlot]:
    if not doctor.is_active or not doctor.user.is_active:
        return []
    zone = ZoneInfo(clinic_timezone)
    day_start = datetime.combine(day, time.min, zone)
    day_end = datetime.combine(day + timedelta(days=1), time.min, zone)
    schedules = db.scalars(select(Availability).where(
        Availability.doctor_id == doctor.id,
        Availability.weekday == day.weekday(),
        Availability.is_active.is_(True),
    ).order_by(Availability.start_time))
    blocked = list(db.execute(select(
        DoctorUnavailability.start_at, DoctorUnavailability.end_at,
    ).where(
        DoctorUnavailability.doctor_id == doctor.id,
        DoctorUnavailability.start_at < day_end,
        DoctorUnavailability.end_at > day_start,
    )))
    bookings = select(Appointment.start_at, Appointment.end_at).where(
        Appointment.doctor_id == doctor.id,
        Appointment.status != "cancelled",
        Appointment.start_at < day_end,
        Appointment.end_at > day_start,
    )
    if exclude_id is not None:
        bookings = bookings.where(Appointment.id != exclude_id)
    blocked.extend(db.execute(bookings))
    now = datetime.now(timezone.utc)
    slots = []
    for schedule in schedules:
        start = datetime.combine(day, schedule.start_time, zone)
        end = datetime.combine(day, schedule.end_time, zone)
        duration = timedelta(minutes=schedule.slot_duration_minutes)
        while start + duration <= end:
            slot_end = start + duration
            if start > now and not any(
                start < blocked_end and slot_end > blocked_start
                for blocked_start, blocked_end in blocked
            ):
                slots.append(AvailableSlot(start_at=start, end_at=slot_end))
            start = slot_end
    # Older walk-ins have no reservation; conservatively retain their capacity.
    unreserved_visits = db.scalar(select(func.count()).select_from(Visit).where(
        Visit.doctor_id == doctor.id,
        Visit.visit_date == day,
        Visit.appointment_id.is_(None),
        Visit.status != "cancelled",
    )) or 0
    return slots[unreserved_visits:]


def select_slot(
    db: Session, doctor: Doctor, start_at: datetime, clinic_timezone: str,
    exclude_id: int | None = None,
) -> AvailableSlot:
    if start_at <= datetime.now(timezone.utc):
        raise BadRequestError("Appointment must start in the future.")
    day = start_at.astimezone(ZoneInfo(clinic_timezone)).date()
    for slot in available_slots(db, doctor, day, clinic_timezone, exclude_id):
        if slot.start_at == start_at:
            return slot
    raise ConflictError("The selected appointment slot is not available.")


def create_appointment(
    db: Session, doctor: Doctor, data: AppointmentCreate, clinic_timezone: str,
) -> Appointment:
    get_patient(db, data.patient_id)
    slot = select_slot(db, doctor, data.start_at, clinic_timezone)
    appointment = Appointment(
        doctor_id=doctor.id, patient_id=data.patient_id,
        start_at=slot.start_at, end_at=slot.end_at,
        status="scheduled",
    )
    db.add(appointment)
    return appointment


def get_appointment(db: Session, appointment_id: int) -> Appointment:
    appointment = db.get(Appointment, appointment_id)
    if appointment is None:
        raise NotFoundError("Appointment")
    return appointment


def reschedule_appointment(
    db: Session, doctor: Doctor, appointment: Appointment,
    start_at: datetime, clinic_timezone: str,
) -> Appointment:
    ensure_not_checked_in(db, appointment)
    if appointment.status != "scheduled":
        raise ConflictError("Only scheduled appointments can be rescheduled.")
    if appointment.start_at <= datetime.now(timezone.utc):
        raise ConflictError("An appointment that has started cannot be rescheduled.")
    slot = select_slot(db, doctor, start_at, clinic_timezone, appointment.id)
    appointment.start_at = slot.start_at
    appointment.end_at = slot.end_at
    return appointment


def cancel_appointment(db: Session, appointment: Appointment) -> Appointment:
    ensure_not_checked_in(db, appointment)
    if appointment.status == "cancelled":
        return appointment
    if appointment.status != "scheduled":
        raise ConflictError("Only scheduled appointments can be cancelled.")
    appointment.status = "cancelled"
    return appointment


def ensure_not_checked_in(db: Session, appointment: Appointment) -> None:
    if db.scalar(select(Visit.id).where(Visit.appointment_id == appointment.id)):
        raise ConflictError("This appointment is checked in. Manage its visit instead.")



def mark_no_show(db: Session, appointment: Appointment) -> Appointment:
    ensure_not_checked_in(db, appointment)
    if appointment.status == "no_show":
        return appointment
    if appointment.status != "scheduled":
        raise ConflictError("Only scheduled appointments can be marked as no-show.")
    if appointment.end_at > datetime.now(timezone.utc):
        raise ConflictError("An appointment can be marked as no-show only after it ends.")
    appointment.status = "no_show"
    return appointment


def list_appointments(
    db: Session, user: User, clinic_timezone: str, *, doctor_id: int | None,
    patient_id: int | None, date_from: date | None, date_to: date | None,
    status: str | None, offset: int, limit: int,
) -> AppointmentPage:

    if date_from is not None and date_to is not None and date_from > date_to:
        raise BadRequestError("date_from must not be after date_to.")
    filters = []
    if user.role == UserRole.DOCTOR:
        if user.doctor is None or (doctor_id is not None and doctor_id != user.doctor.id):
            raise ForbiddenError("You can view only your own appointments.")
        doctor_id = user.doctor.id
    if doctor_id is not None:
        get_booking_doctor(db, doctor_id)
        filters.append(Appointment.doctor_id == doctor_id)
    if patient_id is not None:
        filters.append(Appointment.patient_id == patient_id)
    zone = ZoneInfo(clinic_timezone)
    if date_from is not None:
        filters.append(Appointment.start_at >= datetime.combine(date_from, time.min, zone))
    if date_to is not None:
        if date_to == date.max:
            raise BadRequestError("date_to must be earlier than 9999-12-31.")
        filters.append(Appointment.start_at < datetime.combine(date_to + timedelta(days=1), time.min, zone))
    if status is not None:
        filters.append(Appointment.status == status)
    rows = db.scalars(select(Appointment).where(*filters).order_by(
        Appointment.start_at, Appointment.id,
    ).offset(offset).limit(limit))
    return AppointmentPage(items=[AppointmentRead.model_validate(row) for row in rows],
                           total=db.scalar(select(func.count()).select_from(Appointment).where(*filters)),
                           offset=offset, limit=limit)
