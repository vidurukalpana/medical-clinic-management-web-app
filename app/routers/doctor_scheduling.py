from fastapi import APIRouter, Response, status

from app.dependencies import (
    DatabaseSession,
    ScheduleAvailability,
    ScheduleDoctor,
    ScheduleManagerDoctor,
    ScheduleUnavailability,
)
from app.schemas.doctor_scheduling import (
    AvailabilityCreate,
    AvailabilityRead,
    DoctorUnavailabilityCreate,
    DoctorUnavailabilityRead,
)
from app.services.doctor_scheduling import (
    create_availability,
    create_unavailability,
    delete_availability,
    delete_unavailability,
    list_availability,
    list_unavailability,
    update_availability,
    update_unavailability,
)

router = APIRouter(
    prefix="/doctors/{doctor_id}",
    tags=["doctor scheduling"],
)


@router.get(
    "/availability",
    response_model=list[AvailabilityRead],
    summary="List a doctor's weekly availability",
)
def read_availability(
    doctor: ScheduleDoctor,
    db: DatabaseSession,
) -> list[AvailabilityRead]:
    return [
        AvailabilityRead.model_validate(item)
        for item in list_availability(db, doctor.id)
    ]


@router.post(
    "/availability",
    response_model=AvailabilityRead,
    status_code=status.HTTP_201_CREATED,
    summary="Add a weekly availability period",
    responses={409: {"description": "Availability period overlaps"}},
)
def add_availability(
    schedule: AvailabilityCreate,
    doctor: ScheduleManagerDoctor,
    db: DatabaseSession,
) -> AvailabilityRead:
    availability = create_availability(db, doctor.id, schedule)
    return AvailabilityRead.model_validate(availability)


@router.put(
    "/availability/{availability_id}",
    response_model=AvailabilityRead,
    summary="Replace a weekly availability period",
    responses={409: {"description": "Availability period overlaps"}},
)
def replace_availability(
    schedule: AvailabilityCreate,
    availability: ScheduleAvailability,
    db: DatabaseSession,
) -> AvailabilityRead:
    availability = update_availability(db, availability, schedule)
    return AvailabilityRead.model_validate(availability)


@router.delete(
    "/availability/{availability_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a weekly availability period",
)
def remove_availability(
    availability: ScheduleAvailability,
    db: DatabaseSession,
) -> Response:
    delete_availability(db, availability)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/unavailability",
    response_model=list[DoctorUnavailabilityRead],
    summary="List a doctor's unavailable periods",
)
def read_unavailability(
    doctor: ScheduleDoctor,
    db: DatabaseSession,
) -> list[DoctorUnavailabilityRead]:
    return [
        DoctorUnavailabilityRead.model_validate(item)
        for item in list_unavailability(db, doctor.id)
    ]


@router.post(
    "/unavailability",
    response_model=DoctorUnavailabilityRead,
    status_code=status.HTTP_201_CREATED,
    summary="Add an unavailable period",
    responses={409: {"description": "Unavailable period overlaps"}},
)
def add_unavailability(
    unavailable_period: DoctorUnavailabilityCreate,
    doctor: ScheduleManagerDoctor,
    db: DatabaseSession,
) -> DoctorUnavailabilityRead:
    unavailability = create_unavailability(
        db,
        doctor.id,
        unavailable_period,
    )
    return DoctorUnavailabilityRead.model_validate(unavailability)


@router.put(
    "/unavailability/{unavailability_id}",
    response_model=DoctorUnavailabilityRead,
    summary="Replace an unavailable period",
    responses={409: {"description": "Unavailable period overlaps"}},
)
def replace_unavailability(
    unavailable_period: DoctorUnavailabilityCreate,
    unavailability: ScheduleUnavailability,
    db: DatabaseSession,
) -> DoctorUnavailabilityRead:
    unavailability = update_unavailability(
        db,
        unavailability,
        unavailable_period,
    )
    return DoctorUnavailabilityRead.model_validate(unavailability)


@router.delete(
    "/unavailability/{unavailability_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove an unavailable period",
)
def remove_unavailability(
    unavailability: ScheduleUnavailability,
    db: DatabaseSession,
) -> Response:
    delete_unavailability(db, unavailability)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
