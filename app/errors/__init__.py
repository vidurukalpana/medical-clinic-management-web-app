"""Application error definitions."""

from app.errors.exceptions import (
    ApplicationError,
    AuthenticationRequiredError,
    AvailabilityOverlapError,
    BadRequestError,
    ChatbotUnavailableError,
    ConflictError,
    DuplicateRegistrationNumberError,
    DoctorFullyBookedError,
    ForbiddenError,
    InvalidCredentialsError,
    InvalidCurrentPasswordError,
    NotFoundError,
    ServiceUnavailableError,
    UnavailabilityOverlapError,
)

__all__ = [
    "ApplicationError",
    "AuthenticationRequiredError",
    "AvailabilityOverlapError",
    "BadRequestError",
    "ChatbotUnavailableError",
    "ConflictError",
    "DuplicateRegistrationNumberError",
    "DoctorFullyBookedError",
    "ForbiddenError",
    "InvalidCredentialsError",
    "InvalidCurrentPasswordError",
    "NotFoundError",
    "ServiceUnavailableError",
    "UnavailabilityOverlapError",
]
