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
from app.models import Appointment, Availability, Doctor, DoctorUnavailability
from app.schemas.doctor_scheduling import (
    AvailabilityCreate,
    DoctorUnavailabilityCreate,
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

    ensure_bookings_covered(db, availability, schedule, clinic_timezone)
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
) -> None:
    periods = list(db.scalars(select(Availability).where(
        Availability.doctor_id == original.doctor_id,
        Availability.id != original.id, Availability.is_active.is_(True),
    )))
    if replacement is not None and replacement.is_active:
        periods.append(replacement)
    bookings = db.scalars(select(Appointment).where(
        Appointment.doctor_id == original.doctor_id,
        Appointment.status == "scheduled",
        Appointment.end_at > datetime.now(timezone.utc),
    ))
    zone = ZoneInfo(clinic_timezone)
    for booking in bookings:
        start, end = booking.start_at.astimezone(zone), booking.end_at.astimezone(zone)
        # Only protect bookings covered by the period being changed.
        if not (original.is_active and start.weekday() == original.weekday
                and start.date() == end.date()
                and original.start_time <= start.time() and end.time() <= original.end_time):
            continue
        if not any(period.weekday == start.weekday()
                   and period.start_time <= start.time() and end.time() <= period.end_time
                   for period in periods):
            raise ConflictError("Working hours conflict with an existing booking. Reschedule or cancel it first.")
