"""Handle visit transaction failures outside the service layer."""

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.errors import ConflictError


def save_visit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        constraint = getattr(getattr(error.orig, "diag", None), "constraint_name", None)
        if constraint in (
            "uq_visit_queue", "uq_visit_active_patient", "visits_appointment_id_key",
            "uq_appointment_doctor_start",
        ):
            raise ConflictError("The patient or appointment is already queued. Refresh the queue.") from error
        raise
    except SQLAlchemyError:
        db.rollback()
        raise
