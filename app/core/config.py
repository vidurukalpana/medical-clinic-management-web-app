from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIRECTORY = PROJECT_ROOT / "data"
DATA_DIRECTORY.mkdir(exist_ok=True)
DEFAULT_DATABASE_URL = f"sqlite+pysqlite:///{DATA_DIRECTORY / 'medical_clinic.db'}"


class Settings(BaseSettings):
    app_name: str = "Medical Clinic Management"
    app_version: str = "0.1.0"
    debug: bool = True
    database_url: str = DEFAULT_DATABASE_URL
    timezone: str = "Asia/Colombo"
    host: str = "127.0.0.1"
    port: int = 8000
    secret_key: SecretStr = SecretStr("local-development-only")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="CLINIC_",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
