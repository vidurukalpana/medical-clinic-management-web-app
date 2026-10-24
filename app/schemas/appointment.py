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


class SessionTime(BaseModel):
    start_at: datetime
    end_at: datetime


class BookingSession(SessionTime):
    max_patients: int
    remaining: int
    # Places online booking may still take; the rest are kept for walk-ins and reception.
    remaining_online: int


class AppointmentRead(SessionTime):
    model_config = ConfigDict(from_attributes=True)

    id: int
    doctor_id: int
    patient_id: int
    appointment_number: int
    status: Literal["scheduled", "completed", "cancelled", "no_show"]
    cancelled_by_clinic: bool
    checkin_code: str


class BookingStatus(BaseModel):
    remaining_places: int
    remaining_online_places: int
    is_fully_booked: bool


class GuestBookingCreate(AppointmentReschedule):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    doctor_id: int = Field(gt=0)
    full_name: str = Field(min_length=2, max_length=150)
    phone: str = Field(pattern=r"^\+?[0-9][0-9 ()-]{5,28}[0-9]$")


class GuestBookingRead(SessionTime):
    model_config = ConfigDict(from_attributes=True)

    id: int
    doctor_id: int
    appointment_number: int
    status: Literal["scheduled", "completed", "cancelled", "no_show"]
    cancelled_by_clinic: bool
    checkin_code: str


class GuestBookingConfirmation(GuestBookingRead):
    management_token: str


class AppointmentPage(BaseModel):
    items: list[AppointmentRead]
    total: int
    offset: int
    limit: int


class CheckInLookup(BaseModel):
    """What reception sees after scanning a booking's QR code."""

    appointment_id: int
    appointment_number: int
    status: Literal["scheduled", "completed", "cancelled", "no_show"]
    patient_name: str
    doctor_id: int
    doctor_name: str
    start_at: datetime
    end_at: datetime
    visit_id: int | None
    queue_number: int | None
    can_check_in: bool
    # Why the booking cannot be checked in, in words reception can say to the patient.
    problem: str | None
