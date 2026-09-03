"""Application exceptions that are independent of FastAPI."""


class ApplicationError(Exception):
    """Base class for expected application errors."""

    default_detail = "An application error occurred."

    def __init__(self, detail: str | None = None) -> None:
        self.detail = detail or self.default_detail
        super().__init__(self.detail)


class BadRequestError(ApplicationError):
    """Raised when a valid request cannot be processed."""


class InvalidCurrentPasswordError(BadRequestError):
    """Raised when the supplied current password is incorrect."""

    default_detail = "Current password is incorrect."


class AuthenticationRequiredError(ApplicationError):
    """Raised when a request has no valid authenticated session."""

    default_detail = "Authentication required."


class InvalidCredentialsError(AuthenticationRequiredError):
    """Raised when login credentials are incorrect."""

    default_detail = "Incorrect username or password."


class ForbiddenError(ApplicationError):
    """Raised when an authenticated user lacks permission."""


class NotFoundError(ApplicationError):
    """Raised when a requested resource does not exist."""

    def __init__(self, resource: str) -> None:
        super().__init__(f"{resource} not found.")


class ConflictError(ApplicationError):
    """Raised when a requested change conflicts with existing data."""


class DuplicateRegistrationNumberError(ConflictError):
    """Raised when a doctor's registration number is already used."""

    default_detail = "Registration number already exists."


class AvailabilityOverlapError(ConflictError):
    """Raised when active weekly availability periods overlap."""

    default_detail = "Availability period overlaps an existing active period."


class UnavailabilityOverlapError(ConflictError):
    """Raised when doctor unavailability periods overlap."""

    default_detail = "Unavailable period overlaps an existing period."
