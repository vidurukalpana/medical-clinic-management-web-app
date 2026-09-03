from datetime import datetime, time

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class AvailabilityCreate(BaseModel):
    weekday: int = Field(ge=0, le=4)
    start_time: time
    end_time: time
    slot_duration_minutes: int = Field(ge=5, le=240)
    is_active: bool = True

    @model_validator(mode="after")
    def validate_working_period(self) -> "AvailabilityCreate":
        start_seconds = _time_in_seconds(self.start_time)
        end_seconds = _time_in_seconds(self.end_time)
        if start_seconds >= end_seconds:
            raise ValueError("start_time must be earlier than end_time.")

        working_minutes = (end_seconds - start_seconds) / 60
        if self.slot_duration_minutes > working_minutes:
            raise ValueError(
                "slot_duration_minutes must fit within the availability period."
            )
        return self


class AvailabilityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    doctor_id: int
    weekday: int
    start_time: time
    end_time: time
    slot_duration_minutes: int
    is_active: bool


class DoctorUnavailabilityCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    start_at: datetime
    end_at: datetime
    reason: str | None = Field(default=None, max_length=255)

    @field_validator("reason", mode="after")
    @classmethod
    def empty_reason_is_none(cls, value: str | None) -> str | None:
        return value or None

    @model_validator(mode="after")
    def validate_unavailable_period(self) -> "DoctorUnavailabilityCreate":
        if self.start_at.tzinfo is None or self.end_at.tzinfo is None:
            raise ValueError("start_at and end_at must include a timezone offset.")
        if self.start_at >= self.end_at:
            raise ValueError("start_at must be earlier than end_at.")
        return self


class DoctorUnavailabilityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    doctor_id: int
    start_at: datetime
    end_at: datetime
    reason: str | None


def _time_in_seconds(value: time) -> int:
    return value.hour * 3600 + value.minute * 60 + value.second
