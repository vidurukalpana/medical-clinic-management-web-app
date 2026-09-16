from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.appointment import Appointment

from app.db.base import Base


class Visit(Base):
    __tablename__ = "visits"
    __table_args__ = (
        UniqueConstraint("doctor_id", "visit_date", "queue_number", name="uq_visit_queue"),
        CheckConstraint("queue_number > 0", name="ck_visit_queue_number"),
        CheckConstraint(
            "status IN ('waiting', 'in_progress', 'completed', 'cancelled')",
            name="ck_visit_status",
        ),
        Index(
            "uq_visit_active_patient", "doctor_id", "visit_date", "patient_id",
            unique=True, postgresql_where=text("status IN ('waiting', 'in_progress')"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    appointment_id: Mapped[int | None] = mapped_column(
        ForeignKey("appointments.id"), unique=True, nullable=True,
    )
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id"), index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    visit_date: Mapped[date] = mapped_column(Date)
    queue_number: Mapped[int]
    status: Mapped[str] = mapped_column(String(20), default="waiting")
    presenting_complaint: Mapped[str | None] = mapped_column(Text)
    diagnosis: Mapped[str | None] = mapped_column(Text)
    clinical_notes: Mapped[str | None] = mapped_column(Text)
    treatment_plan: Mapped[str | None] = mapped_column(Text)

    appointment: Mapped[Appointment | None] = relationship()

    @property
    def start_at(self) -> datetime | None:
        return self.appointment.start_at if self.appointment else None

    @property
    def end_at(self) -> datetime | None:
        return self.appointment.end_at if self.appointment else None
