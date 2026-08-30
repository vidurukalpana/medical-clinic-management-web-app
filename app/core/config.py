from functools import lru_cache

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

POSTGRESQL_URL_PREFIX = "postgresql+psycopg://"
DEFAULT_DATABASE_URL = (
    "postgresql+psycopg://clinic_app:change-this-password@"
    "127.0.0.1:5432/medical_clinic"
)


class Settings(BaseSettings):
    app_name: str = "Medical Clinic Management"
    app_version: str = "0.1.0"
    debug: bool = True
    database_url: str = DEFAULT_DATABASE_URL
    timezone: str = "Asia/Colombo"
    host: str = "127.0.0.1"
    port: int = 8000
    secret_key: SecretStr = SecretStr("local-development-only")
    session_expire_hours: int = Field(default=12, ge=1, le=168)

    admin_username: str = "admin"
    admin_password: SecretStr | None = None
    doctor_one_username: str = "doctor1"
    doctor_one_password: SecretStr | None = None
    doctor_two_username: str = "doctor2"
    doctor_two_password: SecretStr | None = None

    @field_validator("database_url")
    @classmethod
    def require_postgresql(cls, value: str) -> str:
        if not value.startswith(POSTGRESQL_URL_PREFIX):
            raise ValueError(
                "CLINIC_DATABASE_URL must use PostgreSQL with the psycopg driver."
            )
        return value

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="CLINIC_",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
