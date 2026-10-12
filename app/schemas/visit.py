from datetime import date, datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

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
    appointment_number: int | None
    start_at: datetime | None
    end_at: datetime | None
    status: VisitStatus
    checked_in_at: datetime | None
    consult_started_at: datetime | None
    consult_ended_at: datetime | None


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


class QueueSession(BaseModel):
    """The doctor's current or next session today."""

    start_at: datetime
    end_at: datetime
    doctor_arrived_at: datetime | None


class SeenVisit(BaseModel):
    id: int
    appointment_number: int | None
    patient_name: str
    consult_started_at: datetime | None
    consult_ended_at: datetime | None


class DoctorQueue(BaseModel):
    doctor_id: int
    doctor_name: str
    is_active: bool
    waiting_count: int
    in_progress_count: int
    session: QueueSession | None
    patients: list[DashboardVisit]
    # Completed today, most recent first.
    seen: list[SeenVisit]


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


class LiveSession(BaseModel):
    """Public progress of one session: numbers only, never patient details."""

    doctor_id: int
    doctor_name: str
    start_at: datetime
    end_at: datetime
    status: Literal["not_started", "in_progress", "ended", "unavailable"]
    doctor_arrived_at: datetime | None
    now_serving: int | None
    numbers_to_see: list[int]


class LiveQueueRead(BaseModel):
    day: date
    generated_at: datetime
    sessions: list[LiveSession]


class SessionArrive(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_at: AwareDatetime


class SessionArrivalRead(BaseModel):
    start_at: datetime
    doctor_arrived_at: datetime
