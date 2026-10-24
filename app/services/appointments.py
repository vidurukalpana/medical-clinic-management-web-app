from datetime import date, datetime, time, timedelta, timezone
from itertools import count
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.errors import BadRequestError, ConflictError, ForbiddenError, NotFoundError
from app.models import Appointment, Availability, Doctor, DoctorUnavailability, User, UserRole, Visit
from app.schemas.appointment import AppointmentCreate, AppointmentPage, AppointmentRead, BookingSession
from app.services.patients import get_patient


def get_booking_doctor(db: Session, doctor_id: int, *, lock: bool = False) -> Doctor:
    statement = select(Doctor).where(Doctor.id == doctor_id)
    if lock:
        statement = statement.with_for_update()
    doctor = db.scalar(statement)
    if doctor is None:
        raise NotFoundError("Doctor")
    return doctor


def booking_sessions(
    db: Session, doctor: Doctor, day: date, clinic_timezone: str,
    exclude_id: int | None = None,
) -> list[BookingSession]:
    """The day's sessions that have not ended and are not blocked, including full ones."""
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
    # Only online bookings carry a private-code hash.
    online = func.count().filter(Appointment.guest_token_hash.is_not(None))
    bookings = select(Appointment.start_at, func.count(), online).where(
        Appointment.doctor_id == doctor.id,
        Appointment.status != "cancelled",
        Appointment.start_at >= day_start,
        Appointment.start_at < day_end,
    ).group_by(Appointment.start_at)
    if exclude_id is not None:
        bookings = bookings.where(Appointment.id != exclude_id)
    booked = {start: (total, online_total) for start, total, online_total in db.execute(bookings)}
    # Older walk-ins have no reservation; conservatively retain their capacity.
    unreserved_visits = db.scalar(select(func.count()).select_from(Visit).where(
        Visit.doctor_id == doctor.id,
        Visit.visit_date == day,
        Visit.appointment_id.is_(None),
        Visit.status != "cancelled",
    )) or 0
    now = datetime.now(timezone.utc)
    sessions = []
    for schedule in schedules:
        start = datetime.combine(day, schedule.start_time, zone)
        end = datetime.combine(day, schedule.end_time, zone)
        # Time off anywhere in a session closes the whole session.
        if end <= now or any(start < blocked_end and end > blocked_start
                             for blocked_start, blocked_end in blocked):
            continue
        total, online_total = booked.get(start, (0, 0))
        remaining = max(schedule.max_patients - total, 0)
        held = min(remaining, unreserved_visits)
        unreserved_visits -= held
        remaining -= held
        online_cap = schedule.max_patients - schedule.reserved_places
        sessions.append(BookingSession(
            start_at=start, end_at=end, max_patients=schedule.max_patients, remaining=remaining,
            remaining_online=max(min(online_cap - online_total, remaining), 0),
        ))
    return sessions


def select_session(
    db: Session, doctor: Doctor, start_at: datetime, clinic_timezone: str,
    exclude_id: int | None = None, *, online: bool = False,
) -> BookingSession:
    zone = ZoneInfo(clinic_timezone)
    day = start_at.astimezone(zone).date()
    if day < datetime.now(zone).date():
        raise BadRequestError("Choose a session from today onwards.")
    for session in booking_sessions(db, doctor, day, clinic_timezone, exclude_id):
        if session.start_at == start_at:
            if not session.remaining:
                raise ConflictError("This session is fully booked.")
            if online and not session.remaining_online:
                raise ConflictError(
                    "Online booking for this session is full. Reception may still have places.",
                )
            return session
    raise ConflictError("The selected session is not available.")


def next_appointment_number(
    db: Session, doctor_id: int, start_at: datetime, exclude_id: int | None = None,
) -> int:
    """The lowest number not held in the session, so a cancelled number is reused."""
    statement = select(Appointment.appointment_number).where(
        Appointment.doctor_id == doctor_id,
        Appointment.start_at == start_at,
        Appointment.status != "cancelled",
    )
    if exclude_id is not None:
        statement = statement.where(Appointment.id != exclude_id)
    taken = set(db.scalars(statement))
    return next(number for number in count(1) if number not in taken)


def create_appointment(
    db: Session, doctor: Doctor, data: AppointmentCreate, clinic_timezone: str,
    *, online: bool = False,
) -> Appointment:
    get_patient(db, data.patient_id)
    session = select_session(db, doctor, data.start_at, clinic_timezone, online=online)
    appointment = Appointment(
        doctor_id=doctor.id, patient_id=data.patient_id,
        start_at=session.start_at, end_at=session.end_at,
        appointment_number=next_appointment_number(db, doctor.id, session.start_at),
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
    start_at: datetime, clinic_timezone: str, *, online: bool = False,
) -> Appointment:
    # A patient whose session the clinic cancelled may move to another session.
    rebooking = appointment.status == "cancelled" and appointment.cancelled_by_clinic
    if rebooking and db.scalar(select(Visit.id).where(Visit.appointment_id == appointment.id)):
        raise ConflictError("You had checked in before the session was cancelled. Please ask reception to book again.")
    ensure_not_checked_in(db, appointment)
    if appointment.status != "scheduled" and not rebooking:
        raise ConflictError("Only scheduled appointments can be rescheduled.")
    if not rebooking and appointment.start_at <= datetime.now(timezone.utc):
        raise ConflictError("An appointment whose session has started cannot be rescheduled.")
    if not rebooking and start_at == appointment.start_at:
        # Already in this session; keep the patient's number.
        return appointment
    # A displaced patient already held a place, so places kept for walk-ins are open to them.
    session = select_session(db, doctor, start_at, clinic_timezone, appointment.id,
                             online=online and not rebooking)
    if rebooking:
        appointment.status = "scheduled"
        appointment.cancelled_by_clinic = False
    appointment.start_at = session.start_at
    appointment.end_at = session.end_at
    appointment.appointment_number = next_appointment_number(
        db, doctor.id, session.start_at, appointment.id,
    )
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
        raise ConflictError("An appointment can be marked as no-show only after its session ends.")
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
        Appointment.start_at, Appointment.appointment_number, Appointment.id,
    ).offset(offset).limit(limit))
    return AppointmentPage(items=[AppointmentRead.model_validate(row) for row in rows],
                           total=db.scalar(select(func.count()).select_from(Appointment).where(*filters)),
                           offset=offset, limit=limit)
