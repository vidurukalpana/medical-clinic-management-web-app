from fastapi import APIRouter, HTTPException, Response, status

from app.dependencies import AdministratorUser, DatabaseSession
from app.models import User
from app.schemas.auth import PasswordResetRequest
from app.services.auth import set_user_password

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
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    set_user_password(db, user, request.new_password)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
