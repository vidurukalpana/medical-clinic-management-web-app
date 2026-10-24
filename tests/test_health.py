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
