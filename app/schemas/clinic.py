from pydantic import BaseModel, ConfigDict, Field


class ClinicContact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    address_lines: list[str] = Field(min_length=1, max_length=5)
    phone: str = Field(min_length=1, max_length=30)
    whatsapp: str | None = Field(default=None, max_length=30)
    email: str | None = Field(default=None, max_length=254)
    reception_hours: str = Field(min_length=1, max_length=100)
    closed_days: str | None = Field(default=None, max_length=100)
    emergency_number: str | None = Field(default=None, max_length=20)
