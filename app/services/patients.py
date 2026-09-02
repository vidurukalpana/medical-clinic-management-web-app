from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.patient import Patient, patient_record_number_sequence
from app.schemas.patient import PatientCreate, PatientUpdate


def create_patient(db: Session, patient_data: PatientCreate) -> Patient:
    next_record_number = db.scalar(
        select(patient_record_number_sequence.next_value())
    )
    if next_record_number is None:
        raise RuntimeError("Could not generate a medical record number.")

    patient = Patient(
        medical_record_number=f"MRN-{next_record_number:06d}",
        **patient_data.model_dump(),
    )
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return patient


def get_patient(db: Session, patient_id: int) -> Patient | None:
    return db.get(Patient, patient_id)


def search_patients(
    db: Session,
    query: str | None,
    offset: int,
    limit: int,
) -> tuple[list[Patient], int]:
    statement = select(Patient)
    count_statement = select(func.count()).select_from(Patient)

    normalized_query = query.strip() if query else ""
    if normalized_query:
        escaped_query = _escape_like_pattern(normalized_query)
        pattern = f"%{escaped_query}%"
        search_filter = or_(
            Patient.medical_record_number.ilike(pattern, escape="\\"),
            Patient.full_name.ilike(pattern, escape="\\"),
            Patient.phone.ilike(pattern, escape="\\"),
        )
        statement = statement.where(search_filter)
        count_statement = count_statement.where(search_filter)

    statement = (
        statement.order_by(Patient.full_name, Patient.id).offset(offset).limit(limit)
    )
    patients = list(db.scalars(statement))
    total = db.scalar(count_statement) or 0
    return patients, total


def update_patient(
    db: Session,
    patient: Patient,
    patient_data: PatientUpdate,
) -> Patient:
    for field_name, value in patient_data.model_dump(exclude_unset=True).items():
        setattr(patient, field_name, value)
    db.commit()
    db.refresh(patient)
    return patient


def _escape_like_pattern(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
