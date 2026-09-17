from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models import UserRole


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    role: UserRole
    is_active: bool


class DoctorProfileCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    display_name: str = Field(min_length=2, max_length=100)
    registration_number: str = Field(min_length=2, max_length=50)
    phone: str | None = Field(default=None, max_length=30)


class UserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_.-]+$")
    password: str = Field(min_length=12, max_length=128)
    role: UserRole
    is_active: bool = True
    doctor: DoctorProfileCreate | None = None

    @model_validator(mode="after")
    def validate_profile(self) -> "UserCreate":
        if (self.role == UserRole.DOCTOR) != (self.doctor is not None):
            raise ValueError("A doctor profile is required only for doctor accounts.")
        return self


class UserUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: UserRole | None = None
    is_active: bool | None = None
    doctor: DoctorProfileCreate | None = None

    @model_validator(mode="after")
    def validate_update(self) -> "UserUpdate":
        if not self.model_fields_set or any(
            getattr(self, field) is None for field in self.model_fields_set
        ):
            raise ValueError("Provide a non-null account update.")
        return self


class UserPage(BaseModel):
    items: list[UserRead]
    total: int
    offset: int
    limit: int
