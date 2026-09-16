from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

VisitStatus = Literal["waiting", "in_progress", "completed", "cancelled"]


class VisitCheckIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    presenting_complaint: str | None = Field(default=None, max_length=10000)


class WalkInCreate(VisitCheckIn):
    doctor_id: int = Field(gt=0)
    patient_id: int = Field(gt=0)


class VisitUpdate(VisitCheckIn):
    status: VisitStatus | None = None
    diagnosis: str | None = Field(default=None, max_length=10000)
    clinical_notes: str | None = Field(default=None, max_length=20000)
    treatment_plan: str | None = Field(default=None, max_length=10000)

    @field_validator("status")
    @classmethod
    def status_cannot_be_null(cls, value: VisitStatus | None) -> VisitStatus:
        if value is None:
            raise ValueError("status cannot be null.")
        return value

    @model_validator(mode="after")
    def require_changes(self) -> "VisitUpdate":
        if not self.model_fields_set:
            raise ValueError("Provide at least one field to update.")
        return self


class VisitRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    appointment_id: int | None
    doctor_id: int
    patient_id: int
    visit_date: date
    queue_number: int
    start_at: datetime | None
    end_at: datetime | None
    status: VisitStatus
    presenting_complaint: str | None
    diagnosis: str | None
    clinical_notes: str | None
    treatment_plan: str | None
