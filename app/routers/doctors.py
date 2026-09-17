from fastapi import APIRouter

from app.dependencies import (
    AdministratorUser,
    CurrentDoctor,
    DatabaseSession,
)
from app.schemas.doctor import DoctorAdminUpdate, DoctorRead, DoctorSelfUpdate, DoctorPublicRead
from app.errors import NotFoundError
from app.services.doctors import get_doctor, list_doctors, update_doctor

router = APIRouter(prefix="/doctors", tags=["doctors"])


@router.get(
    "",
    response_model=list[DoctorPublicRead],
    summary="List doctor profiles",
)
def read_doctors(
    db: DatabaseSession,
) -> list[DoctorPublicRead]:
    doctors = list_doctors(db)
    return [DoctorPublicRead.model_validate(doctor) for doctor in doctors]


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


@router.get("/{doctor_id}", response_model=DoctorPublicRead, summary="Get a public doctor profile")
def read_doctor(doctor_id: int, db: DatabaseSession) -> DoctorPublicRead:
    doctor = get_doctor(db, doctor_id)
    if not doctor.is_active or not doctor.user.is_active:
        raise NotFoundError("Doctor")
    return DoctorPublicRead.model_validate(doctor)


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
    doctor = update_doctor(db, doctor, update)
    return DoctorRead.model_validate(doctor)
