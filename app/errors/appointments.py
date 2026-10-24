"""Transaction error handling for appointment writes, separate from services."""

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.errors import ConflictError


def save_appointment(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        constraint = getattr(getattr(error.orig, "diag", None), "constraint_name", None)
        if constraint == "uq_appointment_session_number":
            raise ConflictError("That number was just taken. Please try again.") from error
        raise
    except SQLAlchemyError:
        db.rollback()
        raise
