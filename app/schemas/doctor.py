from pydantic import BaseModel, ConfigDict, Field, model_validator


class DoctorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    display_name: str
    registration_number: str
    phone: str | None
    is_active: bool


class DoctorSelfUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=2, max_length=100)
    phone: str | None = Field(default=None, max_length=30)

    @model_validator(mode="after")
    def require_an_update(self) -> "DoctorSelfUpdate":
        if not self.model_fields_set:
            raise ValueError("Provide at least one field to update.")
        if "display_name" in self.model_fields_set and self.display_name is None:
            raise ValueError("display_name cannot be null.")
        return self


class DoctorAdminUpdate(DoctorSelfUpdate):
    registration_number: str | None = Field(
        default=None, min_length=2, max_length=50
    )
    is_active: bool | None = None

    @model_validator(mode="after")
    def require_non_null_admin_fields(self) -> "DoctorAdminUpdate":
        if (
            "registration_number" in self.model_fields_set
            and self.registration_number is None
        ):
            raise ValueError("registration_number cannot be null.")
        if "is_active" in self.model_fields_set and self.is_active is None:
            raise ValueError("is_active cannot be null.")
        return self
