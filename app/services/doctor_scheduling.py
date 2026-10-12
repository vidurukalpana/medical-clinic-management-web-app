from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import (
    AvailabilityOverlapError,
    ConflictError,
    NotFoundError,
    UnavailabilityOverlapError,
)
from app.models import Appointment, Availability, Doctor, DoctorUnavailability, Patient, Visit
from app.schemas.doctor_scheduling import (
    AffectedBooking,
    AvailabilityCreate,
    DoctorUnavailabilityCreate,
    SessionCancel,
    SessionCancellationRead,
)


def list_availability(db: Session, doctor_id: int) -> list[Availability]:
    return list(
        db.scalars(
            select(Availability)
            .where(Availability.doctor_id == doctor_id)
            .order_by(
                Availability.weekday,
                Availability.start_time,
                Availability.id,
            )
        )
    )


def create_availability(
    db: Session,
    doctor_id: int,
    schedule: AvailabilityCreate,
) -> Availability:
    lock_schedule(db, doctor_id)
    if _availability_overlaps(db, doctor_id, schedule):
        raise AvailabilityOverlapError()

    availability = Availability(doctor_id=doctor_id, **schedule.model_dump())
    db.add(availability)
    db.commit()
    db.refresh(availability)
    return availability


def get_availability(
    db: Session,
    doctor_id: int,
    availability_id: int,
) -> Availability:
    availability = db.scalar(
        select(Availability).where(
            Availability.id == availability_id,
            Availability.doctor_id == doctor_id,
        )
    )
    if availability is None:
        raise NotFoundError("Availability period")
    return availability


def update_availability(
    db: Session,
    availability: Availability,
    schedule: AvailabilityCreate,
    clinic_timezone: str,
) -> Availability:
    lock_schedule(db, availability.doctor_id)
    db.refresh(availability)
    if _availability_overlaps(
        db,
        availability.doctor_id,
        schedule,
        exclude_id=availability.id,
    ):
        raise AvailabilityOverlapError()

    bookings = ensure_bookings_covered(db, availability, schedule, clinic_timezone)
    zone = ZoneInfo(clinic_timezone)
    for booking in bookings:
        # Keep booked sessions in step with a new end time.
        booking.end_at = datetime.combine(booking.start_at.astimezone(zone).date(), schedule.end_time, zone)
    for field_name, value in schedule.model_dump().items():
        setattr(availability, field_name, value)
    db.commit()
    db.refresh(availability)
    return availability


def delete_availability(db: Session, availability: Availability, clinic_timezone: str) -> None:
    lock_schedule(db, availability.doctor_id)
    db.refresh(availability)
    ensure_bookings_covered(db, availability, None, clinic_timezone)
    db.delete(availability)
    db.commit()


def list_unavailability(
    db: Session,
    doctor_id: int,
) -> list[DoctorUnavailability]:
    return list(
        db.scalars(
            select(DoctorUnavailability)
            .where(DoctorUnavailability.doctor_id == doctor_id)
            .order_by(
                DoctorUnavailability.start_at,
                DoctorUnavailability.id,
            )
        )
    )


def create_unavailability(
    db: Session,
    doctor_id: int,
    unavailable_period: DoctorUnavailabilityCreate,
) -> DoctorUnavailability:
    lock_schedule(db, doctor_id)
    ensure_no_booking_conflict(db, doctor_id, unavailable_period)
    if _unavailability_overlaps(db, doctor_id, unavailable_period):
        raise UnavailabilityOverlapError()

    unavailability = DoctorUnavailability(
        doctor_id=doctor_id,
        **unavailable_period.model_dump(),
    )
    db.add(unavailability)
    db.commit()
    db.refresh(unavailability)
    return unavailability


def get_unavailability(
    db: Session,
    doctor_id: int,
    unavailability_id: int,
) -> DoctorUnavailability:
    unavailability = db.scalar(
        select(DoctorUnavailability).where(
            DoctorUnavailability.id == unavailability_id,
            DoctorUnavailability.doctor_id == doctor_id,
        )
    )
    if unavailability is None:
        raise NotFoundError("Unavailable period")
    return unavailability


def update_unavailability(
    db: Session,
    unavailability: DoctorUnavailability,
    unavailable_period: DoctorUnavailabilityCreate,
) -> DoctorUnavailability:
    lock_schedule(db, unavailability.doctor_id)
    db.refresh(unavailability)
    ensure_no_booking_conflict(db, unavailability.doctor_id, unavailable_period)
    if _unavailability_overlaps(
        db,
        unavailability.doctor_id,
        unavailable_period,
        exclude_id=unavailability.id,
    ):
        raise UnavailabilityOverlapError()

    for field_name, value in unavailable_period.model_dump().items():
        setattr(unavailability, field_name, value)
    db.commit()
    db.refresh(unavailability)
    return unavailability


def delete_unavailability(
    db: Session,
    unavailability: DoctorUnavailability,
) -> None:
    lock_schedule(db, unavailability.doctor_id)
    db.refresh(unavailability)
    db.delete(unavailability)
    db.commit()


def _availability_overlaps(
    db: Session,
    doctor_id: int,
    schedule: AvailabilityCreate,
    exclude_id: int | None = None,
) -> bool:
    if not schedule.is_active:
        return False

    statement = select(Availability.id).where(
        Availability.doctor_id == doctor_id,
        Availability.weekday == schedule.weekday,
        Availability.is_active.is_(True),
        Availability.start_time < schedule.end_time,
        Availability.end_time > schedule.start_time,
    )
    if exclude_id is not None:
        statement = statement.where(Availability.id != exclude_id)
    return db.scalar(statement) is not None


def _unavailability_overlaps(
    db: Session,
    doctor_id: int,
    unavailable_period: DoctorUnavailabilityCreate,
    exclude_id: int | None = None,
) -> bool:
    statement = select(DoctorUnavailability.id).where(
        DoctorUnavailability.doctor_id == doctor_id,
        DoctorUnavailability.start_at < unavailable_period.end_at,
        DoctorUnavailability.end_at > unavailable_period.start_at,
    )
    if exclude_id is not None:
        statement = statement.where(DoctorUnavailability.id != exclude_id)
    return db.scalar(statement) is not None


def lock_schedule(db: Session, doctor_id: int) -> None:
    # Share the booking/check-in lock so validation and mutation are atomic.
    db.execute(select(Doctor.id).where(Doctor.id == doctor_id).with_for_update())


def ensure_no_booking_conflict(
    db: Session, doctor_id: int, period: DoctorUnavailabilityCreate,
) -> None:
    conflict = db.scalar(select(Appointment.id).where(
        Appointment.doctor_id == doctor_id,
        Appointment.status == "scheduled",
        Appointment.end_at > datetime.now(timezone.utc),
        Appointment.start_at < period.end_at,
        Appointment.end_at > period.start_at,
    ))
    if conflict is not None:
        raise ConflictError("Unavailable period conflicts with an existing booking. Reschedule or cancel it first.")


def ensure_bookings_covered(
    db: Session, original: Availability, replacement: AvailabilityCreate | None,
    clinic_timezone: str,
) -> list[Appointment]:
    """Return the session's upcoming bookings, refusing changes that would strand them."""
    if not original.is_active:
        return []
    zone = ZoneInfo(clinic_timezone)
    bookings = [
        booking for booking in db.scalars(select(Appointment).where(
            Appointment.doctor_id == original.doctor_id,
            Appointment.status == "scheduled",
            Appointment.end_at > datetime.now(timezone.utc),
        ))
        # A booking belongs to the session that starts at its start time.
        if booking.start_at.astimezone(zone).weekday() == original.weekday
        and booking.start_at.astimezone(zone).time() == original.start_time
    ]
    if not bookings:
        return []
    if (replacement is None or not replacement.is_active
            or replacement.weekday != original.weekday
            or replacement.start_time != original.start_time):
        raise ConflictError("This session has upcoming bookings. Reschedule or cancel them first.")
    if max(booking.appointment_number for booking in bookings) > replacement.max_patients:
        raise ConflictError("Upcoming bookings already hold numbers above this limit.")
    return bookings


def cancel_session(
    db: Session, doctor_id: int, data: SessionCancel, clinic_timezone: str,
) -> SessionCancellationRead:
    """Close one session on one date and cancel its bookings so patients can move them."""
    lock_schedule(db, doctor_id)
    zone = ZoneInfo(clinic_timezone)
    local_start = data.start_at.astimezone(zone)
    schedule = db.scalar(select(Availability).where(
        Availability.doctor_id == doctor_id,
        Availability.weekday == local_start.weekday(),
        Availability.start_time == local_start.time(),
        Availability.is_active.is_(True),
    ))
    if schedule is None:
        raise NotFoundError("Session")
    end_at = datetime.combine(local_start.date(), schedule.end_time, zone)
    if end_at <= datetime.now(timezone.utc):
        raise ConflictError("This session has already ended.")
    period = DoctorUnavailabilityCreate(start_at=data.start_at, end_at=end_at, reason=data.reason)
    if _unavailability_overlaps(db, doctor_id, period):
        raise ConflictError("This session is already closed by time off.")
    rows = db.execute(
        select(Appointment, Visit, Patient.full_name, Patient.phone)
        .join(Patient, Patient.id == Appointment.patient_id)
        .outerjoin(Visit, Visit.appointment_id == Appointment.id)
        .where(Appointment.doctor_id == doctor_id, Appointment.start_at == data.start_at,
               Appointment.status == "scheduled")
        .order_by(Appointment.appointment_number)
    ).all()
    if any(visit is not None and visit.status == "in_progress" for _, visit, _, _ in rows):
        raise ConflictError("A patient is with the doctor. Finish that visit before cancelling the session.")
    for appointment, visit, _, _ in rows:
        appointment.status = "cancelled"
        appointment.cancelled_by_clinic = True
        if visit is not None:
            visit.status = "cancelled"
    db.add(DoctorUnavailability(
        doctor_id=doctor_id, start_at=data.start_at, end_at=end_at,
        reason=data.reason or "Session cancelled",
    ))
    db.commit()
    return SessionCancellationRead(start_at=data.start_at, end_at=end_at, affected=[
        AffectedBooking(appointment_id=appointment.id, appointment_number=appointment.appointment_number,
                        patient_name=name, phone=phone)
        for appointment, _, name, phone in rows
    ])
