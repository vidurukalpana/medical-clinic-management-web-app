from datetime import date, datetime, timezone
from enum import StrEnum

from sqlalchemy import Date, DateTime, Enum, Sequence, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

patient_record_number_sequence = Sequence(
    "patient_record_number_sequence",
    metadata=Base.metadata,
)


class PatientGender(StrEnum):
    FEMALE = "female"
    MALE = "male"
    OTHER = "other"
    NOT_SPECIFIED = "not_specified"


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(primary_key=True)
    medical_record_number: Mapped[str] = mapped_column(
        String(20), unique=True, index=True
    )
    full_name: Mapped[str] = mapped_column(String(150), index=True)
    date_of_birth: Mapped[date] = mapped_column(Date)
    gender: Mapped[PatientGender] = mapped_column(
        Enum(PatientGender, native_enum=False, length=20, validate_strings=True)
    )
    phone: Mapped[str] = mapped_column(String(30), index=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    emergency_contact: Mapped[str | None] = mapped_column(
        String(200), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
