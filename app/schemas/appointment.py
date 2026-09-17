from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class AppointmentReschedule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_at: AwareDatetime


class AppointmentCreate(AppointmentReschedule):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    doctor_id: int = Field(gt=0)
    patient_id: int = Field(gt=0)


class AvailableSlot(BaseModel):
    start_at: datetime
    end_at: datetime


class AppointmentRead(AvailableSlot):
    model_config = ConfigDict(from_attributes=True)

    id: int
    doctor_id: int
    patient_id: int
    status: Literal["scheduled", "completed", "cancelled", "no_show"]


class BookingStatus(BaseModel):
    remaining_slots: int
    is_fully_booked: bool


class GuestBookingCreate(AppointmentReschedule):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    doctor_id: int = Field(gt=0)
    full_name: str = Field(min_length=2, max_length=150)
    phone: str = Field(pattern=r"^\+?[0-9][0-9 ()-]{5,28}[0-9]$")


class GuestBookingRead(AvailableSlot):
    model_config = ConfigDict(from_attributes=True)

    id: int
    doctor_id: int
    status: Literal["scheduled", "completed", "cancelled", "no_show"]


class GuestBookingConfirmation(GuestBookingRead):
    management_token: str
