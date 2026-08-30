from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.core.config import Settings


def configured_password(password: SecretStr | None) -> str:
    assert password is not None
    return password.get_secret_value()


def login(
    client: TestClient,
    username: str,
    password: str,
) -> tuple[str, dict]:
    response = client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200
    response_body = response.json()
    return response_body["access_token"], response_body


def bearer_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_initial_accounts_include_two_doctors(
    client: TestClient,
    test_settings: Settings,
) -> None:
    admin_token, login_body = login(
        client,
        test_settings.admin_username,
        configured_password(test_settings.admin_password),
    )

    assert login_body["token_type"] == "bearer"
    assert login_body["user"]["role"] == "administrator"
    assert login_body["user"]["doctor"] is None

    response = client.get("/api/doctors", headers=bearer_header(admin_token))

    assert response.status_code == 200
    assert [doctor["display_name"] for doctor in response.json()] == [
        "Doctor One",
        "Doctor Two",
    ]


def test_login_rejects_incorrect_credentials(
    client: TestClient,
    test_settings: Settings,
) -> None:
    response = client.post(
        "/api/auth/login",
        json={
            "username": test_settings.admin_username,
            "password": "incorrect-password",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect username or password."


def test_protected_endpoint_requires_login(client: TestClient) -> None:
    response = client.get("/api/doctors")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_logout_revokes_the_current_session(
    client: TestClient,
    test_settings: Settings,
) -> None:
    token, _ = login(
        client,
        test_settings.doctor_one_username,
        configured_password(test_settings.doctor_one_password),
    )
    headers = bearer_header(token)

    assert client.get("/api/auth/me", headers=headers).status_code == 200
    assert client.post("/api/auth/logout", headers=headers).status_code == 204
    assert client.get("/api/auth/me", headers=headers).status_code == 401


def test_user_can_change_their_password(
    client: TestClient,
    test_settings: Settings,
) -> None:
    old_password = configured_password(test_settings.doctor_one_password)
    new_password = "UpdatedDoctorPassword123!"
    token, _ = login(client, test_settings.doctor_one_username, old_password)
    headers = bearer_header(token)

    change_response = client.put(
        "/api/auth/password",
        headers=headers,
        json={
            "current_password": old_password,
            "new_password": new_password,
        },
    )
    old_password_login = client.post(
        "/api/auth/login",
        json={
            "username": test_settings.doctor_one_username,
            "password": old_password,
        },
    )

    assert change_response.status_code == 204
    assert client.get("/api/auth/me", headers=headers).status_code == 401
    assert old_password_login.status_code == 401
    login(client, test_settings.doctor_one_username, new_password)


def test_incorrect_current_password_does_not_change_password(
    client: TestClient,
    test_settings: Settings,
) -> None:
    current_password = configured_password(test_settings.doctor_one_password)
    token, _ = login(
        client,
        test_settings.doctor_one_username,
        current_password,
    )
    headers = bearer_header(token)

    response = client.put(
        "/api/auth/password",
        headers=headers,
        json={
            "current_password": "IncorrectPassword123!",
            "new_password": "UpdatedDoctorPassword123!",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Current password is incorrect."
    assert client.get("/api/auth/me", headers=headers).status_code == 200


def test_administrator_can_reset_a_user_password(
    client: TestClient,
    test_settings: Settings,
) -> None:
    doctor_password = configured_password(test_settings.doctor_one_password)
    doctor_token, doctor_login = login(
        client,
        test_settings.doctor_one_username,
        doctor_password,
    )
    doctor_user_id = doctor_login["user"]["id"]
    admin_token, _ = login(
        client,
        test_settings.admin_username,
        configured_password(test_settings.admin_password),
    )
    new_password = "AdministratorReset123!"

    reset_response = client.put(
        f"/api/admin/users/{doctor_user_id}/password",
        headers=bearer_header(admin_token),
        json={"new_password": new_password},
    )
    old_password_login = client.post(
        "/api/auth/login",
        json={
            "username": test_settings.doctor_one_username,
            "password": doctor_password,
        },
    )

    assert reset_response.status_code == 204
    assert (
        client.get("/api/auth/me", headers=bearer_header(doctor_token)).status_code
        == 401
    )
    assert old_password_login.status_code == 401
    login(client, test_settings.doctor_one_username, new_password)


def test_doctor_cannot_reset_a_user_password(
    client: TestClient,
    test_settings: Settings,
) -> None:
    doctor_token, doctor_login = login(
        client,
        test_settings.doctor_one_username,
        configured_password(test_settings.doctor_one_password),
    )

    response = client.put(
        f"/api/admin/users/{doctor_login['user']['id']}/password",
        headers=bearer_header(doctor_token),
        json={"new_password": "DoctorCannotReset123!"},
    )

    assert response.status_code == 403


def test_doctor_can_update_only_their_own_profile(
    client: TestClient,
    test_settings: Settings,
) -> None:
    doctor_token, login_body = login(
        client,
        test_settings.doctor_one_username,
        configured_password(test_settings.doctor_one_password),
    )
    headers = bearer_header(doctor_token)
    own_doctor_id = login_body["user"]["doctor"]["id"]

    own_profile = client.get("/api/doctors/me", headers=headers)
    own_update = client.patch(
        "/api/doctors/me",
        headers=headers,
        json={"phone": "+94 77 123 4567"},
    )
    forbidden_admin_update = client.patch(
        f"/api/doctors/{own_doctor_id}",
        headers=headers,
        json={"display_name": "Changed by admin only"},
    )

    assert own_profile.status_code == 200
    assert own_profile.json()["id"] == own_doctor_id
    assert own_update.status_code == 200
    assert own_update.json()["phone"] == "+94 77 123 4567"
    assert forbidden_admin_update.status_code == 403


def test_administrator_can_manage_doctor_profiles(
    client: TestClient,
    test_settings: Settings,
) -> None:
    admin_token, _ = login(
        client,
        test_settings.admin_username,
        configured_password(test_settings.admin_password),
    )
    admin_headers = bearer_header(admin_token)
    doctors = client.get("/api/doctors", headers=admin_headers).json()
    doctor_id = doctors[0]["id"]

    response = client.patch(
        f"/api/doctors/{doctor_id}",
        headers=admin_headers,
        json={"display_name": "Dr. Updated", "registration_number": "DOC-101"},
    )

    assert response.status_code == 200
    assert response.json()["display_name"] == "Dr. Updated"
    assert response.json()["registration_number"] == "DOC-101"


def test_administrator_cannot_use_doctor_self_service_endpoint(
    client: TestClient,
    test_settings: Settings,
) -> None:
    admin_token, _ = login(
        client,
        test_settings.admin_username,
        configured_password(test_settings.admin_password),
    )

    response = client.get("/api/doctors/me", headers=bearer_header(admin_token))

    assert response.status_code == 403
    assert response.json()["detail"] == "Doctor permission required."


def test_registration_numbers_must_be_unique(
    client: TestClient,
    test_settings: Settings,
) -> None:
    admin_token, _ = login(
        client,
        test_settings.admin_username,
        configured_password(test_settings.admin_password),
    )
    headers = bearer_header(admin_token)
    doctors = client.get("/api/doctors", headers=headers).json()

    response = client.patch(
        f"/api/doctors/{doctors[0]['id']}",
        headers=headers,
        json={"registration_number": doctors[1]["registration_number"]},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Registration number already exists."


def test_inactive_doctor_cannot_log_in(
    client: TestClient,
    test_settings: Settings,
) -> None:
    admin_token, _ = login(
        client,
        test_settings.admin_username,
        configured_password(test_settings.admin_password),
    )
    admin_headers = bearer_header(admin_token)
    doctors = client.get("/api/doctors", headers=admin_headers).json()
    doctor_id = doctors[0]["id"]

    deactivate_response = client.patch(
        f"/api/doctors/{doctor_id}",
        headers=admin_headers,
        json={"is_active": False},
    )
    login_response = client.post(
        "/api/auth/login",
        json={
            "username": test_settings.doctor_one_username,
            "password": configured_password(test_settings.doctor_one_password),
        },
    )

    assert deactivate_response.status_code == 200
    assert login_response.status_code == 401
