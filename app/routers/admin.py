from fastapi import APIRouter, Response, status
from sqlalchemy import select

from app.models import Doctor
from app.schemas.doctor import DoctorRead

from app.dependencies import AdministratorUser, DatabaseSession
from app.schemas.auth import PasswordResetRequest
from app.services.auth import set_user_password
from app.services.users import get_user

router = APIRouter(prefix="/admin", tags=["administration"])


@router.put(
    "/users/{user_id}/password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Reset a user's password as an administrator",
)
def reset_user_password(
    user_id: int,
    request: PasswordResetRequest,
    _: AdministratorUser,
    db: DatabaseSession,
) -> Response:
    user = get_user(db, user_id)
    set_user_password(db, user, request.new_password)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/doctors", response_model=list[DoctorRead])
def list_all_doctors(_: AdministratorUser, db: DatabaseSession) -> list[DoctorRead]:
    """Include inactive profiles and staff fields for administrator management."""
    return [DoctorRead.model_validate(doctor) for doctor in db.scalars(
        select(Doctor).order_by(Doctor.id),
    )]
