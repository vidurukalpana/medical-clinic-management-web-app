from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.doctor_scheduling import (
        Availability,
        DoctorUnavailability,
    )
    from app.models.user import User


class Doctor(Base):
    __tablename__ = "doctors"
    __table_args__ = (
        CheckConstraint("consultation_fee >= 0", name="ck_doctor_consultation_fee"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )
    display_name: Mapped[str] = mapped_column(String(100))
    registration_number: Mapped[str] = mapped_column(
        String(50), unique=True, index=True
    )
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    # Public profile shown to patients.
    specialty: Mapped[str | None] = mapped_column(String(80), nullable=True)
    qualifications: Mapped[str | None] = mapped_column(String(200), nullable=True)
    languages: Mapped[str | None] = mapped_column(String(120), nullable=True)
    bio: Mapped[str | None] = mapped_column(String(500), nullable=True)
    consultation_fee: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    user: Mapped[User] = relationship(back_populates="doctor")
    availability: Mapped[list[Availability]] = relationship(
        back_populates="doctor",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    unavailability: Mapped[list[DoctorUnavailability]] = relationship(
        back_populates="doctor",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
