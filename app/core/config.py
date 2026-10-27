from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL, make_url

POSTGRESQL_URL_PREFIX = "postgresql+psycopg://"
DEFAULT_DATABASE_URL = (
    "postgresql+psycopg://clinic_app:change-this-password@"
    "127.0.0.1:5432/medical_clinic"
)
# Passwords from the example env files, refused outside debug mode.
PLACEHOLDER_PASSWORDS = frozenset({
    "change-this-password", "adminpassword", "doctor1password", "doctor2password",
})
MINIMUM_INITIAL_PASSWORD_LENGTH = 12


class Settings(BaseSettings):
    app_name: str = "Medical Clinic Management"
    app_version: str = "0.1.0"
    debug: bool = False
    database_url: str = DEFAULT_DATABASE_URL
    # When a host is set (as on AWS, from the database secret), the URL is built from these parts instead.
    database_host: str | None = None
    database_port: int = 5432
    database_name: str = "medical_clinic"
    database_user: str = "clinic_app"
    database_password: SecretStr | None = None
    # Added to the URL as sslmode, e.g. "require" to refuse unencrypted database connections.
    database_ssl_mode: Literal["disable", "prefer", "require", "verify-ca", "verify-full"] | None = None
    timezone: str = "Asia/Colombo"
    host: str = "127.0.0.1"
    port: int = 8000
    session_expire_hours: int = Field(default=12, ge=1, le=168)
    # Per-address limits on login, registration, guest booking and the chat assistant.
    rate_limit_enabled: bool = True
    # Behind a reverse proxy, its address; uvicorn then takes the client address from X-Forwarded-For.
    trusted_proxy_ips: str = "127.0.0.1"
    # A header in which the CDN in front of the API puts the visitor's IP address, e.g. "X-Viewer-Address".
    # Only set this when every request passes through that CDN and it overwrites the header,
    # or clients could pick their own address.
    client_address_header: str | None = None

    admin_username: str = "admin"
    admin_password: SecretStr | None = None
    doctor_one_username: str = "doctor1"
    doctor_one_password: SecretStr | None = None
    doctor_two_username: str = "doctor2"
    doctor_two_password: SecretStr | None = None
    # Used only by the demo data script, as JSON: {"demo.ayesha": "password", ...}.
    demo_doctor_passwords: dict[str, SecretStr] = {}

    chatbot_base_url: str = "http://127.0.0.1:11434"
    chatbot_model: str = "llama3.2:1b"
    chatbot_timeout_seconds: float = Field(default=60, gt=0, le=300)

    # "outbox" records messages without sending them; add a provider here to send for real.
    sms_provider: Literal["outbox"] = "outbox"
    # Runs in the API process: queues due reminders and hands queued messages to the provider.
    sms_worker_enabled: bool = True
    sms_worker_interval_seconds: int = Field(default=60, ge=5, le=3600)
    # Reminder at this hour on the day, or this many hours before the session, whichever is later.
    sms_reminder_hour: int = Field(default=7, ge=0, le=23)
    sms_reminder_hours_before: int = Field(default=3, ge=0, le=24)

    @field_validator("database_url")
    @classmethod
    def require_postgresql(cls, value: str) -> str:
        if not value.startswith(POSTGRESQL_URL_PREFIX):
            raise ValueError(
                "CLINIC_DATABASE_URL must use PostgreSQL with the psycopg driver."
            )
        return value

    @model_validator(mode="after")
    def build_database_url(self) -> "Settings":
        """Assemble the URL from its parts on AWS, and add the TLS mode if one is set."""
        if not self.database_host and not self.database_ssl_mode:
            return self
        if self.database_host:
            password = self.database_password.get_secret_value() if self.database_password else None
            url = URL.create(
                "postgresql+psycopg", username=self.database_user, password=password,
                host=self.database_host, port=self.database_port, database=self.database_name,
            )
        else:
            url = make_url(self.database_url)
        if self.database_ssl_mode:
            url = url.update_query_dict({"sslmode": self.database_ssl_mode})
        self.database_url = url.render_as_string(hide_password=False)
        return self

    @model_validator(mode="after")
    def refuse_placeholder_secrets(self) -> "Settings":
        """Outside debug mode, refuse to start with example or short account passwords."""
        if self.debug:
            return self
        for name in ("admin_password", "doctor_one_password", "doctor_two_password"):
            secret = getattr(self, name)
            if secret is None:
                continue
            password = secret.get_secret_value()
            if password in PLACEHOLDER_PASSWORDS or len(password) < MINIMUM_INITIAL_PASSWORD_LENGTH:
                raise ValueError(
                    f"CLINIC_{name.upper()} must be a real password of "
                    f"{MINIMUM_INITIAL_PASSWORD_LENGTH}+ characters when CLINIC_DEBUG is off."
                )
        return self

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="CLINIC_",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
