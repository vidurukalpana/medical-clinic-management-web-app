from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator


class AppointmentReschedule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_at: AwareDatetime


class AppointmentCreate(AppointmentReschedule):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    doctor_id: int = Field(gt=0)
    patient_id: int = Field(gt=0)
    reason: str | None = Field(default=None, max_length=255)

    @field_validator("reason")
    @classmethod
    def empty_reason_is_none(cls, value: str | None) -> str | None:
        return value or None


class AvailableSlot(BaseModel):
    start_at: datetime
    end_at: datetime


class AppointmentRead(AvailableSlot):
    model_config = ConfigDict(from_attributes=True)

    id: int
    doctor_id: int
    patient_id: int
    reason: str | None
    status: Literal["scheduled", "completed", "cancelled", "no_show"]
