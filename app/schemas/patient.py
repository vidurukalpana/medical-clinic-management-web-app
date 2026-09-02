from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models import PatientGender


class PatientCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    full_name: str = Field(min_length=2, max_length=150)
    date_of_birth: date
    gender: PatientGender
    phone: str = Field(min_length=7, max_length=30)
    address: str | None = Field(default=None, max_length=1000)
    emergency_contact: str | None = Field(default=None, max_length=200)

    @field_validator("date_of_birth")
    @classmethod
    def date_of_birth_cannot_be_in_the_future(cls, value: date) -> date:
        if value > date.today():
            raise ValueError("Date of birth cannot be in the future.")
        return value

    @field_validator("address", "emergency_contact", mode="after")
    @classmethod
    def empty_optional_text_is_none(cls, value: str | None) -> str | None:
        return value or None


class PatientUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    full_name: str | None = Field(default=None, min_length=2, max_length=150)
    date_of_birth: date | None = None
    gender: PatientGender | None = None
    phone: str | None = Field(default=None, min_length=7, max_length=30)
    address: str | None = Field(default=None, max_length=1000)
    emergency_contact: str | None = Field(default=None, max_length=200)

    @field_validator("date_of_birth")
    @classmethod
    def date_of_birth_cannot_be_in_the_future(
        cls, value: date | None
    ) -> date | None:
        if value is not None and value > date.today():
            raise ValueError("Date of birth cannot be in the future.")
        return value

    @field_validator("address", "emergency_contact", mode="after")
    @classmethod
    def empty_optional_text_is_none(cls, value: str | None) -> str | None:
        return value or None

    @model_validator(mode="after")
    def require_an_update(self) -> "PatientUpdate":
        if not self.model_fields_set:
            raise ValueError("Provide at least one field to update.")
        required_fields = {"full_name", "date_of_birth", "gender", "phone"}
        for field_name in required_fields & self.model_fields_set:
            if getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null.")
        return self


class PatientRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    medical_record_number: str
    full_name: str
    date_of_birth: date
    gender: PatientGender
    phone: str
    address: str | None
    emergency_contact: str | None
    created_at: datetime
    updated_at: datetime


class PatientSearchResponse(BaseModel):
    items: list[PatientRead]
    total: int
    offset: int
    limit: int
