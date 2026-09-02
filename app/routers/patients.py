from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.dependencies import CurrentUser, DatabaseSession
from app.schemas.patient import (
    PatientCreate,
    PatientRead,
    PatientSearchResponse,
    PatientUpdate,
)
from app.services.patients import (
    create_patient,
    get_patient,
    search_patients,
    update_patient,
)

router = APIRouter(prefix="/patients", tags=["patients"])


@router.post(
    "",
    response_model=PatientRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register a patient",
)
def register_patient(
    patient_data: PatientCreate,
    _: CurrentUser,
    db: DatabaseSession,
) -> PatientRead:
    return PatientRead.model_validate(create_patient(db, patient_data))


@router.get(
    "",
    response_model=PatientSearchResponse,
    summary="Search and list patients",
)
def read_patients(
    _: CurrentUser,
    db: DatabaseSession,
    query: Annotated[str | None, Query(max_length=100)] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PatientSearchResponse:
    patients, total = search_patients(db, query, offset, limit)
    return PatientSearchResponse(
        items=[PatientRead.model_validate(patient) for patient in patients],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get(
    "/{patient_id}",
    response_model=PatientRead,
    summary="Get patient details",
)
def read_patient(
    patient_id: int,
    _: CurrentUser,
    db: DatabaseSession,
) -> PatientRead:
    patient = get_patient(db, patient_id)
    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found.",
        )
    return PatientRead.model_validate(patient)


@router.patch(
    "/{patient_id}",
    response_model=PatientRead,
    summary="Update patient details",
)
def edit_patient(
    patient_id: int,
    patient_data: PatientUpdate,
    _: CurrentUser,
    db: DatabaseSession,
) -> PatientRead:
    patient = get_patient(db, patient_id)
    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found.",
        )
    return PatientRead.model_validate(update_patient(db, patient, patient_data))
