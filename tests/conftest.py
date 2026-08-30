from collections.abc import Generator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings
from app.db.session import get_db
from main import create_app


@pytest.fixture
def test_settings() -> Settings:
    application_settings = get_settings()
    return Settings(
        _env_file=None,
        debug=False,
        database_url=application_settings.database_url,
        admin_username="admin",
        admin_password=SecretStr("ClinicAdmin123!"),
        doctor_one_username="doctor1",
        doctor_one_password=SecretStr("ClinicDoctor1!"),
        doctor_two_username="doctor2",
        doctor_two_password=SecretStr("ClinicDoctor2!"),
    )


@pytest.fixture
def client(test_settings: Settings) -> Generator[TestClient]:
    schema_name = f"clinic_test_{uuid4().hex}"
    database_engine = create_engine(
        test_settings.database_url,
        pool_pre_ping=True,
    )
    with database_engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema_name}"'))

    test_engine = create_engine(
        test_settings.database_url,
        connect_args={"options": f"-csearch_path={schema_name}"},
        pool_pre_ping=True,
    )
    test_session_factory = sessionmaker(
        bind=test_engine,
        autoflush=False,
        expire_on_commit=False,
    )

    def override_get_db() -> Generator[Session]:
        with test_session_factory() as db:
            yield db

    test_app = create_app(test_engine, test_settings)
    test_app.dependency_overrides[get_db] = override_get_db
    test_app.dependency_overrides[get_settings] = lambda: test_settings

    try:
        with TestClient(test_app) as test_client:
            yield test_client
    finally:
        test_app.dependency_overrides.clear()
        test_engine.dispose()
        with database_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema_name}" CASCADE'))
        database_engine.dispose()
