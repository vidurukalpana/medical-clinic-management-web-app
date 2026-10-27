from fastapi.testclient import TestClient


def test_root(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["status"] == "running"


def test_health_check(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "connected"}


def test_settings_refuse_example_passwords_outside_debug() -> None:
    import pytest
    from pydantic import SecretStr, ValidationError

    from app.core.config import Settings

    for password in ("change-this-password", "short1!"):
        with pytest.raises(ValidationError, match="CLINIC_ADMIN_PASSWORD"):
            Settings(_env_file=None, debug=False, admin_password=SecretStr(password))

    # Local development may keep the example passwords.
    assert Settings(_env_file=None, debug=True, admin_password=SecretStr("adminpassword")).debug
    assert not Settings(_env_file=None).debug


def test_settings_build_database_url_from_parts() -> None:
    from pydantic import SecretStr
    from sqlalchemy.engine import make_url

    from app.core.config import Settings

    settings = Settings(
        _env_file=None, database_host="db.example.internal",
        database_password=SecretStr("p@ss:w/rd"), database_ssl_mode="require",
    )
    url = make_url(settings.database_url)
    assert (url.drivername, url.host, url.port, url.database, url.username) == (
        "postgresql+psycopg", "db.example.internal", 5432, "medical_clinic", "clinic_app",
    )
    assert url.password == "p@ss:w/rd"
    assert dict(url.query) == {"sslmode": "require"}

    # Without a host or TLS mode, the configured URL is used as it is.
    local_url = "postgresql+psycopg://clinic_app:secret@127.0.0.1:5432/medical_clinic"
    assert Settings(_env_file=None, database_url=local_url).database_url == local_url
