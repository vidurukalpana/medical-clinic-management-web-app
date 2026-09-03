from __future__ import annotations

from datetime import datetime, time
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Time,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.doctor import Doctor


class Availability(Base):
    __tablename__ = "availability"
    __table_args__ = (
        CheckConstraint("weekday BETWEEN 0 AND 4", name="ck_availability_weekday"),
        CheckConstraint(
            "start_time < end_time",
            name="ck_availability_time_order",
        ),
        CheckConstraint(
            "slot_duration_minutes BETWEEN 5 AND 240",
            name="ck_availability_slot_duration",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    doctor_id: Mapped[int] = mapped_column(
        ForeignKey("doctors.id", ondelete="CASCADE"), index=True
    )
    weekday: Mapped[int] = mapped_column(Integer)
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    slot_duration_minutes: Mapped[int] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    doctor: Mapped[Doctor] = relationship(back_populates="availability")


class DoctorUnavailability(Base):
    __tablename__ = "doctor_unavailability"
    __table_args__ = (
        CheckConstraint(
            "start_at < end_at",
            name="ck_doctor_unavailability_time_order",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    doctor_id: Mapped[int] = mapped_column(
        ForeignKey("doctors.id", ondelete="CASCADE"), index=True
    )
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    doctor: Mapped[Doctor] = relationship(back_populates="unavailability")
