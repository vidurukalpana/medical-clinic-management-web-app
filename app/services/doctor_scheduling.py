from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import (
    AvailabilityOverlapError,
    NotFoundError,
    UnavailabilityOverlapError,
)
from app.models import Availability, DoctorUnavailability
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
) -> Availability:
    if _availability_overlaps(
        db,
        availability.doctor_id,
        schedule,
        exclude_id=availability.id,
    ):
        raise AvailabilityOverlapError()

    for field_name, value in schedule.model_dump().items():
        setattr(availability, field_name, value)
    db.commit()
    db.refresh(availability)
    return availability


def delete_availability(db: Session, availability: Availability) -> None:
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
