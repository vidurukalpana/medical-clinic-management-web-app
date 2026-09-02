"""Pydantic request and response schemas."""
from app.schemas.auth import (
    AuthenticatedUserRead,
    LoginRequest,
    LoginResponse,
    PasswordChangeRequest,
    PasswordResetRequest,
)
from app.schemas.doctor import DoctorAdminUpdate, DoctorRead, DoctorSelfUpdate
from app.schemas.patient import (
    PatientCreate,
    PatientRead,
    PatientSearchResponse,
    PatientUpdate,
)
from app.schemas.user import UserRead

__all__ = [
    "AuthenticatedUserRead",
    "DoctorAdminUpdate",
    "DoctorRead",
    "DoctorSelfUpdate",
    "LoginRequest",
    "LoginResponse",
    "PasswordChangeRequest",
    "PasswordResetRequest",
    "PatientCreate",
    "PatientRead",
    "PatientSearchResponse",
    "PatientUpdate",
    "UserRead",
]
