from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SessionArrival(Base):
    """When the doctor arrived for, and left, one session on one date, recorded by the server."""

    __tablename__ = "session_arrivals"
    __table_args__ = (UniqueConstraint("doctor_id", "session_start", name="uq_session_arrival"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id", ondelete="CASCADE"), index=True)
    session_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    arrived_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    left_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
