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
) -> tuple[dict[str, str], dict]:
    response = client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200
    body = response.json()
    return {"Authorization": f"Bearer {body['access_token']}"}, body


def availability_payload(**changes: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "weekday": 0,
        "start_time": "09:00:00",
        "end_time": "13:00:00",
        "slot_duration_minutes": 15,
        "is_active": True,
    }
    payload.update(changes)
    return payload


def test_doctor_scheduling_requires_login(client: TestClient) -> None:
    availability_response = client.get("/api/doctors/1/availability")
    unavailability_response = client.get("/api/doctors/1/unavailability")

    assert availability_response.status_code == 401
    assert unavailability_response.status_code == 401


def test_doctor_can_manage_own_availability(
    client: TestClient,
    test_settings: Settings,
) -> None:
    headers, login_body = login(
        client,
        test_settings.doctor_one_username,
        configured_password(test_settings.doctor_one_password),
    )
    doctor_id = login_body["user"]["doctor"]["id"]
    base_url = f"/api/doctors/{doctor_id}/availability"

    friday_response = client.post(
        base_url,
        headers=headers,
        json=availability_payload(
            weekday=4,
            start_time="14:00:00",
            end_time="17:00:00",
        ),
    )
    monday_response = client.post(
        base_url,
        headers=headers,
        json=availability_payload(),
    )
    monday_id = monday_response.json()["id"]
    replacement_response = client.put(
        f"{base_url}/{monday_id}",
        headers=headers,
        json=availability_payload(
            start_time="10:00:00",
            end_time="14:00:00",
            slot_duration_minutes=30,
        ),
    )
    list_response = client.get(base_url, headers=headers)

    assert friday_response.status_code == 201
    assert monday_response.status_code == 201
    assert replacement_response.status_code == 200
    assert replacement_response.json()["id"] == monday_id
    assert replacement_response.json()["slot_duration_minutes"] == 30
    assert [item["weekday"] for item in list_response.json()] == [0, 4]

    overlap_response = client.post(
        base_url,
        headers=headers,
        json=availability_payload(start_time="13:00:00", end_time="15:00:00"),
    )
    delete_response = client.delete(f"{base_url}/{monday_id}", headers=headers)

    assert overlap_response.status_code == 409
    assert delete_response.status_code == 204


def test_availability_validation_rejects_weekends_and_invalid_periods(
    client: TestClient,
    test_settings: Settings,
) -> None:
    headers, login_body = login(
        client,
        test_settings.doctor_one_username,
        configured_password(test_settings.doctor_one_password),
    )
    doctor_id = login_body["user"]["doctor"]["id"]
    base_url = f"/api/doctors/{doctor_id}/availability"

    reversed_hours = client.post(
        base_url,
        headers=headers,
        json=availability_payload(start_time="13:00:00", end_time="09:00:00"),
    )
    duration_too_long = client.post(
        base_url,
        headers=headers,
        json=availability_payload(
            start_time="09:00:00",
            end_time="09:30:00",
            slot_duration_minutes=60,
        ),
    )
    weekend = client.post(
        base_url,
        headers=headers,
        json=availability_payload(weekday=5),
    )

    assert reversed_hours.status_code == 422
    assert duration_too_long.status_code == 422
    assert weekend.status_code == 422


def test_doctor_can_manage_only_own_schedule_and_admin_can_manage_any_schedule(
    client: TestClient,
    test_settings: Settings,
) -> None:
    doctor_headers, doctor_login = login(
        client,
        test_settings.doctor_one_username,
        configured_password(test_settings.doctor_one_password),
    )
    own_doctor_id = doctor_login["user"]["doctor"]["id"]
    doctors = client.get("/api/doctors", headers=doctor_headers).json()
    other_doctor_id = next(
        doctor["id"] for doctor in doctors if doctor["id"] != own_doctor_id
    )

    forbidden_response = client.post(
        f"/api/doctors/{other_doctor_id}/availability",
        headers=doctor_headers,
        json=availability_payload(),
    )
    view_response = client.get(
        f"/api/doctors/{other_doctor_id}/availability",
        headers=doctor_headers,
    )

    admin_headers, _ = login(
        client,
        test_settings.admin_username,
        configured_password(test_settings.admin_password),
    )
    admin_response = client.post(
        f"/api/doctors/{other_doctor_id}/availability",
        headers=admin_headers,
        json=availability_payload(),
    )

    assert forbidden_response.status_code == 403
    assert view_response.status_code == 200
    assert admin_response.status_code == 201


def test_doctor_can_manage_unavailable_periods(
    client: TestClient,
    test_settings: Settings,
) -> None:
    headers, login_body = login(
        client,
        test_settings.doctor_one_username,
        configured_password(test_settings.doctor_one_password),
    )
    doctor_id = login_body["user"]["doctor"]["id"]
    base_url = f"/api/doctors/{doctor_id}/unavailability"

    first_response = client.post(
        base_url,
        headers=headers,
        json={
            "start_at": "2030-12-25T00:00:00+05:30",
            "end_at": "2030-12-26T00:00:00+05:30",
            "reason": "Public holiday",
        },
    )
    second_response = client.post(
        base_url,
        headers=headers,
        json={
            "start_at": "2030-01-10T09:00:00+05:30",
            "end_at": "2030-01-10T12:00:00+05:30",
            "reason": "Conference",
        },
    )
    overlap_response = client.post(
        base_url,
        headers=headers,
        json={
            "start_at": "2030-12-25T10:00:00+05:30",
            "end_at": "2030-12-25T11:00:00+05:30",
            "reason": "Duplicate period",
        },
    )
    list_response = client.get(base_url, headers=headers)

    assert first_response.status_code == 201
    assert second_response.status_code == 201
    assert overlap_response.status_code == 409
    assert [item["reason"] for item in list_response.json()] == [
        "Conference",
        "Public holiday",
    ]

    unavailability_id = first_response.json()["id"]
    update_response = client.put(
        f"{base_url}/{unavailability_id}",
        headers=headers,
        json={
            "start_at": "2030-12-26T00:00:00+05:30",
            "end_at": "2030-12-27T00:00:00+05:30",
            "reason": "Annual leave",
        },
    )
    delete_response = client.delete(
        f"{base_url}/{unavailability_id}",
        headers=headers,
    )

    assert update_response.status_code == 200
    assert update_response.json()["reason"] == "Annual leave"
    assert delete_response.status_code == 204


def test_scheduling_resources_return_not_found(
    client: TestClient,
    test_settings: Settings,
) -> None:
    headers, _ = login(
        client,
        test_settings.admin_username,
        configured_password(test_settings.admin_password),
    )

    missing_doctor = client.get(
        "/api/doctors/999/availability",
        headers=headers,
    )
    missing_availability = client.delete(
        "/api/doctors/1/availability/999",
        headers=headers,
    )
    missing_unavailability = client.delete(
        "/api/doctors/1/unavailability/999",
        headers=headers,
    )

    assert missing_doctor.status_code == 404
    assert missing_availability.status_code == 404
    assert missing_unavailability.status_code == 404
