from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Appointment(Base):
    __tablename__ = "appointments"
    __table_args__ = (
        CheckConstraint("start_at < end_at", name="ck_appointment_time_order"),
        CheckConstraint(
            "status IN ('scheduled', 'completed', 'cancelled', 'no_show')",
            name="ck_appointment_status",
        ),
        Index(
            "uq_appointment_doctor_start", "doctor_id", "start_at",
            unique=True, postgresql_where=text("status <> 'cancelled'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id"), index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="scheduled")
