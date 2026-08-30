from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.auth_session import AuthSession
    from app.models.doctor import Doctor


class UserRole(StrEnum):
    ADMINISTRATOR = "administrator"
    DOCTOR = "doctor"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, native_enum=False, length=20, validate_strings=True)
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    doctor: Mapped[Doctor | None] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        single_parent=True,
    )
    auth_sessions: Mapped[list[AuthSession]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
