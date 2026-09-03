from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.core.config import Settings, get_settings
from app.dependencies import CurrentAuthSession, CurrentUser, DatabaseSession
from app.schemas.auth import (
    AuthenticatedUserRead,
    LoginRequest,
    LoginResponse,
    PasswordChangeRequest,
)
from app.services.auth import (
    authenticate_user,
    change_user_password,
    create_auth_session,
    revoke_auth_session,
)

router = APIRouter(prefix="/auth", tags=["authentication"])
AppSettings = Annotated[Settings, Depends(get_settings)]


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="Log in with a username and password",
    responses={401: {"description": "Incorrect username or password"}},
)
def login(
    credentials: LoginRequest,
    db: DatabaseSession,
    settings: AppSettings,
) -> LoginResponse:
    user = authenticate_user(db, credentials.username, credentials.password)
    access_token, _ = create_auth_session(
        db,
        user,
        expires_in_hours=settings.session_expire_hours,
    )
    return LoginResponse(
        access_token=access_token,
        expires_in=settings.session_expire_hours * 60 * 60,
        user=AuthenticatedUserRead.model_validate(user),
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Log out and revoke the current session",
)
def logout(
    auth_session: CurrentAuthSession,
    db: DatabaseSession,
) -> Response:
    revoke_auth_session(db, auth_session)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/me",
    response_model=AuthenticatedUserRead,
    summary="Get the currently logged-in user",
)
def read_current_user(current_user: CurrentUser) -> AuthenticatedUserRead:
    return AuthenticatedUserRead.model_validate(current_user)


@router.put(
    "/password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Change the current user's password",
    responses={400: {"description": "Current password is incorrect"}},
)
def change_password(
    request: PasswordChangeRequest,
    current_user: CurrentUser,
    db: DatabaseSession,
) -> Response:
    change_user_password(
        db,
        current_user,
        request.current_password,
        request.new_password,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
