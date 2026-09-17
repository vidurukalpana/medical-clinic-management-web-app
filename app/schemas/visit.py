from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.appointment import AppointmentRead

VisitStatus = Literal["waiting", "in_progress", "completed", "cancelled"]


class VisitCheckIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)



class WalkInCreate(VisitCheckIn):
    doctor_id: int = Field(gt=0)
    patient_id: int = Field(gt=0)


class VisitUpdate(VisitCheckIn):
    status: VisitStatus | None = None

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


class DashboardAction(BaseModel):
    label: str
    method: Literal["POST", "PUT", "PATCH"]
    path: str
    body: dict[str, str | int] = Field(default_factory=dict)


class DashboardAppointment(AppointmentRead):
    patient_name: str
    doctor_name: str
    visit_id: int | None
    actions: list[DashboardAction] = Field(default_factory=list)


class DashboardVisit(VisitRead):
    patient_name: str
    actions: list[DashboardAction] = Field(default_factory=list)


class DoctorQueue(BaseModel):
    doctor_id: int
    doctor_name: str
    is_active: bool
    waiting_count: int
    in_progress_count: int
    patients: list[DashboardVisit]


class DashboardSummary(BaseModel):
    appointments: int
    scheduled: int
    waiting: int
    in_progress: int
    completed: int
    cancelled: int
    no_show: int


class DashboardRead(BaseModel):
    day: date
    timezone: str
    generated_at: datetime
    summary: DashboardSummary
    appointments: list[DashboardAppointment]
    doctor_queues: list[DoctorQueue]
