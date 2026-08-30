from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.doctor import DoctorRead
from app.schemas.user import UserRead


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=8, max_length=128)


class AuthenticatedUserRead(UserRead):
    model_config = ConfigDict(from_attributes=True)

    doctor: DoctorRead | None


class LoginResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    user: AuthenticatedUserRead


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=12, max_length=128)

    @model_validator(mode="after")
    def require_a_different_password(self) -> "PasswordChangeRequest":
        if self.current_password == self.new_password:
            raise ValueError("The new password must be different.")
        return self


class PasswordResetRequest(BaseModel):
    new_password: str = Field(min_length=12, max_length=128)
