"""FastAPI handlers for expected application errors."""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.errors.exceptions import (
    ApplicationError,
    AuthenticationRequiredError,
    BadRequestError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
)


def register_error_handlers(application: FastAPI) -> None:
    """Register the application's expected error responses."""
    application.add_exception_handler(ApplicationError, handle_application_error)


async def handle_application_error(
    _: Request,
    error: ApplicationError,
) -> JSONResponse:
    """Convert an expected application error into a JSON API response."""
    status_code = _status_code_for(error)
    headers = (
        {"WWW-Authenticate": "Bearer"}
        if isinstance(error, AuthenticationRequiredError)
        else None
    )
    return JSONResponse(
        status_code=status_code,
        content={"detail": error.detail},
        headers=headers,
    )


def _status_code_for(error: ApplicationError) -> int:
    if isinstance(error, BadRequestError):
        return status.HTTP_400_BAD_REQUEST
    if isinstance(error, AuthenticationRequiredError):
        return status.HTTP_401_UNAUTHORIZED
    if isinstance(error, ForbiddenError):
        return status.HTTP_403_FORBIDDEN
    if isinstance(error, NotFoundError):
        return status.HTTP_404_NOT_FOUND
    if isinstance(error, ConflictError):
        return status.HTTP_409_CONFLICT
    return status.HTTP_500_INTERNAL_SERVER_ERROR
