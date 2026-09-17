from typing import Annotated

from fastapi import APIRouter, Query, Response, status
from sqlalchemy import func, select

from app.dependencies import AdministratorUser, DatabaseSession
from app.models import Doctor, User, UserRole
from app.schemas.auth import AuthenticatedUserRead, PasswordResetRequest
from app.schemas.doctor import DoctorRead
from app.schemas.user import UserCreate, UserPage, UserRead, UserUpdate
from app.services.auth import set_user_password
from app.services.users import create_user, get_user, update_user

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


@router.post("/users", response_model=AuthenticatedUserRead, status_code=201)
def add_user(data: UserCreate, _: AdministratorUser, db: DatabaseSession) -> User:
    return create_user(db, data)


@router.get("/users", response_model=UserPage)
def list_users(
    _: AdministratorUser, db: DatabaseSession,
    role: UserRole | None = None, is_active: bool | None = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> UserPage:
    filters = []
    if role is not None:
        filters.append(User.role == role)
    if is_active is not None:
        filters.append(User.is_active == is_active)
    users = db.scalars(select(User).where(*filters).order_by(User.id).offset(offset).limit(limit))
    return UserPage(items=[UserRead.model_validate(user) for user in users],
                    total=db.scalar(select(func.count()).select_from(User).where(*filters)),
                    offset=offset, limit=limit)


@router.get("/users/{user_id}", response_model=AuthenticatedUserRead)
def read_user(user_id: int, _: AdministratorUser, db: DatabaseSession) -> User:
    return get_user(db, user_id)


@router.patch("/users/{user_id}", response_model=AuthenticatedUserRead)
def edit_user(user_id: int, data: UserUpdate, _: AdministratorUser, db: DatabaseSession) -> User:
    return update_user(db, user_id, data)
