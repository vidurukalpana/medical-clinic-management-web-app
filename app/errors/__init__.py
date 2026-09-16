"""Application error definitions."""

from app.errors.exceptions import (
    ApplicationError,
    AuthenticationRequiredError,
    AvailabilityOverlapError,
    BadRequestError,
    ConflictError,
    DuplicateRegistrationNumberError,
    DoctorFullyBookedError,
    ForbiddenError,
    InvalidCredentialsError,
    InvalidCurrentPasswordError,
    NotFoundError,
    UnavailabilityOverlapError,
)

__all__ = [
    "ApplicationError",
    "AuthenticationRequiredError",
    "AvailabilityOverlapError",
    "BadRequestError",
    "ConflictError",
    "DuplicateRegistrationNumberError",
    "DoctorFullyBookedError",
    "ForbiddenError",
    "InvalidCredentialsError",
    "InvalidCurrentPasswordError",
    "NotFoundError",
    "UnavailabilityOverlapError",
]
