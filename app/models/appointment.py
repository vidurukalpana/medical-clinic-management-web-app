from datetime import datetime
from secrets import choice

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


# No 0/O, 1/I/L, so a code read aloud or typed from a printout is unambiguous.
CHECKIN_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"


def new_checkin_code() -> str:
    return "".join(choice(CHECKIN_ALPHABET) for _ in range(10))


def normalize_checkin_code(value: str) -> str:
    """Accept "k7m2p-qx9rt" or "K7M2P QX9RT" as typed or read from a printout."""
    return "".join(char for char in value.upper() if char.isalnum())


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
    # Shown to the patient as a QR code; on its own it only lets signed-in staff find the booking.
    checkin_code: Mapped[str] = mapped_column(String(12), unique=True, default=new_checkin_code)
