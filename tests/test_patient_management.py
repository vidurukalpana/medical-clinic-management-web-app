from datetime import date, timedelta

from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.core.config import Settings


def configured_password(password: SecretStr | None) -> str:
    assert password is not None
    return password.get_secret_value()


def doctor_login_headers(
    client: TestClient,
    settings: Settings,
) -> dict[str, str]:
    response = client.post(
        "/api/auth/login",
        json={
            "username": settings.doctor_one_username,
            "password": configured_password(settings.doctor_one_password),
        },
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def patient_payload(**changes: str) -> dict[str, str]:
    payload = {
        "full_name": "Nimal Perera",
        "date_of_birth": "1988-04-12",
        "gender": "male",
        "phone": "+94 77 123 4567",
        "address": "12 Lake Road, Colombo",
        "emergency_contact": "Kamal Perera - +94 71 222 3344",
    }
    payload.update(changes)
    return payload


def test_patient_api_requires_login(client: TestClient) -> None:
    response = client.get("/api/patients")

    assert response.status_code == 401


def test_patient_registration_search_details_and_editing_api(
    client: TestClient,
    test_settings: Settings,
) -> None:
    headers = doctor_login_headers(client, test_settings)

    create_response = client.post(
        "/api/patients",
        headers=headers,
        json=patient_payload(),
    )

    assert create_response.status_code == 201
    created_patient = create_response.json()
    assert created_patient["medical_record_number"] == "MRN-000001"
    assert created_patient["full_name"] == "Nimal Perera"

    patient_id = created_patient["id"]
    detail_response = client.get(f"/api/patients/{patient_id}", headers=headers)
    name_search = client.get(
        "/api/patients",
        headers=headers,
        params={"query": "perera"},
    )
    mrn_search = client.get(
        "/api/patients",
        headers=headers,
        params={"query": "MRN-000001"},
    )
    phone_search = client.get(
        "/api/patients",
        headers=headers,
        params={"query": "123 4567"},
    )
    update_response = client.patch(
        f"/api/patients/{patient_id}",
        headers=headers,
        json={"phone": "+94 77 765 4321", "address": ""},
    )

    assert detail_response.status_code == 200
    assert detail_response.json()["id"] == patient_id
    assert name_search.json()["total"] == 1
    assert mrn_search.json()["items"][0]["id"] == patient_id
    assert phone_search.json()["items"][0]["id"] == patient_id
    assert update_response.status_code == 200
    assert update_response.json()["phone"] == "+94 77 765 4321"
    assert update_response.json()["address"] is None


def test_patient_validation_rejects_future_birth_date_and_empty_update(
    client: TestClient,
    test_settings: Settings,
) -> None:
    headers = doctor_login_headers(client, test_settings)
    future_date = (date.today() + timedelta(days=1)).isoformat()

    create_response = client.post(
        "/api/patients",
        headers=headers,
        json=patient_payload(date_of_birth=future_date),
    )
    valid_response = client.post(
        "/api/patients",
        headers=headers,
        json=patient_payload(),
    )
    update_response = client.patch(
        f"/api/patients/{valid_response.json()['id']}",
        headers=headers,
        json={},
    )

    assert create_response.status_code == 422
    assert valid_response.status_code == 201
    assert update_response.status_code == 422


def test_search_treats_sql_wildcards_as_normal_characters(
    client: TestClient,
    test_settings: Settings,
) -> None:
    headers = doctor_login_headers(client, test_settings)
    client.post("/api/patients", headers=headers, json=patient_payload())

    percent_search = client.get(
        "/api/patients",
        headers=headers,
        params={"query": "%"},
    )
    underscore_search = client.get(
        "/api/patients",
        headers=headers,
        params={"query": "_"},
    )

    assert percent_search.status_code == 200
    assert percent_search.json()["total"] == 0
    assert underscore_search.status_code == 200
    assert underscore_search.json()["total"] == 0


def test_missing_patient_returns_not_found(
    client: TestClient,
    test_settings: Settings,
) -> None:
    headers = doctor_login_headers(client, test_settings)

    api_response = client.get("/api/patients/999", headers=headers)
    assert api_response.status_code == 404
    assert api_response.json()["detail"] == "Patient not found."
