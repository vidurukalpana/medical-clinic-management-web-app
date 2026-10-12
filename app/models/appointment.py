from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, text
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
        CheckConstraint("appointment_number > 0", name="ck_appointment_number"),
        Index(
            "uq_appointment_session_number", "doctor_id", "start_at", "appointment_number",
            unique=True, postgresql_where=text("status <> 'cancelled'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id"), index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    # A booking holds a numbered place in a session; start_at/end_at are the session's hours.
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    appointment_number: Mapped[int]
    booked_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    guest_token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="scheduled")
    # Set when staff cancel the whole session; the patient may then move the booking.
    cancelled_by_clinic: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
