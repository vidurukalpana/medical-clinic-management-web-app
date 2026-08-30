from fastapi import APIRouter, HTTPException, status

from app.dependencies import (
    AdministratorUser,
    CurrentDoctor,
    CurrentUser,
    DatabaseSession,
)
from app.models import UserRole
from app.schemas.doctor import DoctorAdminUpdate, DoctorRead, DoctorSelfUpdate
from app.services.doctors import (
    DuplicateRegistrationNumberError,
    get_doctor,
    list_doctors,
    update_doctor,
)

router = APIRouter(prefix="/doctors", tags=["doctors"])


@router.get(
    "",
    response_model=list[DoctorRead],
    summary="List doctor profiles",
)
def read_doctors(
    current_user: CurrentUser,
    db: DatabaseSession,
) -> list[DoctorRead]:
    doctors = list_doctors(
        db,
        include_inactive=current_user.role == UserRole.ADMINISTRATOR,
    )
    return [DoctorRead.model_validate(doctor) for doctor in doctors]


@router.get(
    "/me",
    response_model=DoctorRead,
    summary="Get the current doctor's profile",
)
def read_own_doctor_profile(current_doctor: CurrentDoctor) -> DoctorRead:
    return DoctorRead.model_validate(current_doctor)


@router.patch(
    "/me",
    response_model=DoctorRead,
    summary="Update the current doctor's profile",
)
def update_own_doctor_profile(
    update: DoctorSelfUpdate,
    current_doctor: CurrentDoctor,
    db: DatabaseSession,
) -> DoctorRead:
    doctor = update_doctor(db, current_doctor, update)
    return DoctorRead.model_validate(doctor)


@router.get(
    "/{doctor_id}",
    response_model=DoctorRead,
    summary="Get a doctor profile",
)
def read_doctor(
    doctor_id: int,
    _: CurrentUser,
    db: DatabaseSession,
) -> DoctorRead:
    doctor = get_doctor(db, doctor_id)
    if doctor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor not found.",
        )
    return DoctorRead.model_validate(doctor)


@router.patch(
    "/{doctor_id}",
    response_model=DoctorRead,
    summary="Update any doctor profile as an administrator",
    responses={409: {"description": "Registration number already exists"}},
)
def update_doctor_as_administrator(
    doctor_id: int,
    update: DoctorAdminUpdate,
    _: AdministratorUser,
    db: DatabaseSession,
) -> DoctorRead:
    doctor = get_doctor(db, doctor_id)
    if doctor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor not found.",
        )

    try:
        doctor = update_doctor(db, doctor, update)
    except DuplicateRegistrationNumberError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Registration number already exists.",
        ) from error

    return DoctorRead.model_validate(doctor)
