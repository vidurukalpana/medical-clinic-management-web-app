from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SmsMessage(Base):
    """A text to a patient, written in the same transaction as the booking that caused it."""

    __tablename__ = "sms_outbox"
    __table_args__ = (
        CheckConstraint("kind IN ('confirmation', 'reminder')", name="ck_sms_kind"),
        CheckConstraint("status IN ('queued', 'sent', 'failed', 'logged')", name="ck_sms_status"),
        # One reminder per booking per session, even with several workers.
        Index("uq_sms_reminder", "appointment_id", "session_start", unique=True,
              postgresql_where=text("kind = 'reminder'")),
        Index("ix_sms_queued", "status", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    appointment_id: Mapped[int | None] = mapped_column(
        ForeignKey("appointments.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    session_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    kind: Mapped[str] = mapped_column(String(20))
    phone: Mapped[str] = mapped_column(String(30))
    body: Mapped[str] = mapped_column(Text)
    # queued -> sent | failed; "logged" means recorded with no SMS provider set up.
    status: Mapped[str] = mapped_column(String(10), default="queued")
    error: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
