from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import BadRequestError, ConflictError, NotFoundError
from app.models import Appointment, Availability, Doctor, DoctorUnavailability
from app.schemas.appointment import AppointmentCreate, AvailableSlot
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
    return slots


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
        reason=data.reason, status="scheduled",
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
    if appointment.status != "scheduled":
        raise ConflictError("Only scheduled appointments can be rescheduled.")
    if appointment.start_at <= datetime.now(timezone.utc):
        raise ConflictError("An appointment that has started cannot be rescheduled.")
    slot = select_slot(db, doctor, start_at, clinic_timezone, appointment.id)
    appointment.start_at = slot.start_at
    appointment.end_at = slot.end_at
    return appointment


def cancel_appointment(appointment: Appointment) -> Appointment:
    if appointment.status == "cancelled":
        return appointment
    if appointment.status != "scheduled":
        raise ConflictError("Only scheduled appointments can be cancelled.")
    appointment.status = "cancelled"
    return appointment
