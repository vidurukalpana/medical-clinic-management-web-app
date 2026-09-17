from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from tests.test_doctor_scheduling import availability_payload, configured_password, login


@pytest.fixture
def booking(client, test_settings):
    headers, _ = login(client, "admin", configured_password(test_settings.admin_password))
    doctor_id = client.get("/api/doctors", headers=headers).json()[0]["id"]
    day = datetime.now(ZoneInfo(test_settings.timezone)).date() + timedelta(days=7)
    day += timedelta(days=(0 - day.weekday()) % 7)
    response = client.post(f"/api/doctors/{doctor_id}/availability", headers=headers,
                           json=availability_payload(end_time="10:00:00"))
    assert response.status_code == 201
    patient = client.post("/api/patients", headers=headers, json={
        "full_name": "Booking Patient", "date_of_birth": "1990-01-01",
        "gender": "female", "phone": "0771234567",
    })
    assert patient.status_code == 201
    payload = {"doctor_id": doctor_id, "patient_id": patient.json()["id"],
               "start_at": f"{day}T09:00:00+05:30"}
    return headers, payload, f"/api/doctors/{doctor_id}/available-slots?day={day}"


def test_booking_rescheduling_and_cancellation(client, booking):
    headers, payload, slots_url = booking
    slots = client.get(slots_url, headers=headers).json()
    assert len(slots) == 4
    created = client.post("/api/appointments", headers=headers, json=payload)
    assert created.status_code == 201
    appointment = created.json()
    url = f"/api/appointments/{appointment['id']}"
    assert "reason" not in appointment
    assert appointment["end_at"] == slots[0]["end_at"]
    assert client.get(url, headers=headers).status_code == 200
    assert len(client.get(slots_url, headers=headers).json()) == 3
    assert client.post("/api/appointments", headers=headers, json=payload).status_code == 409
    moved = client.put(url + "/reschedule", headers=headers,
                       json={"start_at": slots[1]["start_at"]})
    assert moved.status_code == 200
    assert client.get(slots_url, headers=headers).json()[0] == slots[0]
    assert client.put(url + "/cancel", headers=headers).json()["status"] == "cancelled"
    assert client.put(url + "/cancel", headers=headers).status_code == 200
    assert len(client.get(slots_url, headers=headers).json()) == 4
    assert client.put(url + "/reschedule", headers=headers,
                      json={"start_at": slots[0]["start_at"]}).status_code == 409
    assert client.post("/api/appointments", headers=headers, json=payload).status_code == 201


def test_unavailability_and_invalid_slots(client, booking):
    headers, payload, slots_url = booking
    start = datetime.fromisoformat(payload["start_at"])
    response = client.post(f"/api/doctors/{payload['doctor_id']}/unavailability",
                           headers=headers, json={
                               "start_at": (start + timedelta(minutes=10)).isoformat(),
                               "end_at": (start + timedelta(minutes=20)).isoformat(),
                           })
    assert response.status_code == 201
    assert len(client.get(slots_url, headers=headers).json()) == 2
    for offset in (0, 15, 31, 60):
        data = {**payload, "start_at": (start + timedelta(minutes=offset)).isoformat()}
        assert client.post("/api/appointments", headers=headers, json=data).status_code == 409
    assert client.post("/api/appointments", headers=headers,
                       json={**payload, "start_at": "2020-01-01T09:00:00+05:30"}).status_code == 400
    assert client.post("/api/appointments", headers=headers,
                       json={**payload, "start_at": "2030-01-01T09:00:00"}).status_code == 422
    assert client.post("/api/appointments", headers=headers,
                       json={**payload, "patient_id": 99999}).status_code == 404
    assert client.get("/api/appointments/99999", headers=headers).status_code == 404
    assert client.get("/api/doctors/99999/available-slots?day=2030-01-01",
                      headers=headers).status_code == 404


def test_failed_reschedule_preserves_original_booking(client, booking):
    headers, payload, slots_url = booking
    slots = client.get(slots_url, headers=headers).json()
    first = client.post("/api/appointments", headers=headers, json=payload).json()
    second = client.post("/api/appointments", headers=headers,
                         json={**payload, "start_at": slots[1]["start_at"]}).json()
    url = f"/api/appointments/{first['id']}"
    assert client.put(url + "/reschedule", headers=headers,
                      json={"start_at": second["start_at"]}).status_code == 409
    assert client.get(url, headers=headers).json()["start_at"] == first["start_at"]


def test_concurrent_booking_has_one_winner(client, booking):
    headers, payload, _ = booking
    def book(_):
        return client.post("/api/appointments", headers=headers, json=payload).status_code
    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(book, range(2))) == [201, 409]


def test_permissions_and_inactive_doctor(client, booking, test_settings):
    headers, payload, slots_url = booking
    assert client.get(slots_url).status_code == 200
    assert client.post("/api/appointments", json=payload).status_code == 401
    created = client.post("/api/appointments", headers=headers, json=payload).json()
    for username, password in (("doctor1", test_settings.doctor_one_password),
                               ("doctor2", test_settings.doctor_two_password)):
        doctor_headers, body = login(client, username, configured_password(password))
        if body["user"]["doctor"]["id"] != payload["doctor_id"]:
            assert client.post("/api/appointments", headers=doctor_headers,
                               json=payload).status_code == 403
            assert client.put(f"/api/appointments/{created['id']}/cancel",
                              headers=doctor_headers).status_code == 403
            assert client.put(f"/api/appointments/{created['id']}/reschedule",
                              headers=doctor_headers,
                              json={"start_at": payload["start_at"]}).status_code == 403
    assert client.patch(f"/api/doctors/{payload['doctor_id']}", headers=headers,
                        json={"is_active": False}).status_code == 200
    assert client.get(slots_url, headers=headers).json() == []
    assert client.post("/api/appointments", headers=headers, json=payload).status_code == 409


def test_schedule_change_does_not_allow_overlapping_booking(client, booking):
    headers, payload, slots_url = booking
    slots = client.get(slots_url, headers=headers).json()
    # The existing 09:15-09:30 appointment overlaps the new 09:00-09:30 slot.
    assert client.post("/api/appointments", headers=headers,
                       json={**payload, "start_at": slots[1]["start_at"]}).status_code == 201
    url = f"/api/doctors/{payload['doctor_id']}/availability"
    schedule_id = client.get(url, headers=headers).json()[0]["id"]
    assert client.put(f"{url}/{schedule_id}", headers=headers,
                      json=availability_payload(end_time="10:00:00",
                                                slot_duration_minutes=30)).status_code == 200
    assert len(client.get(slots_url, headers=headers).json()) == 1
    assert client.post("/api/appointments", headers=headers, json=payload).status_code == 409


def test_equivalent_timezone_and_partial_slot(client, booking):
    headers, payload, slots_url = booking
    url = f"/api/doctors/{payload['doctor_id']}/availability"
    schedule_id = client.get(url, headers=headers).json()[0]["id"]
    assert client.put(f"{url}/{schedule_id}", headers=headers,
                      json=availability_payload(end_time="09:40:00")).status_code == 200
    assert len(client.get(slots_url, headers=headers).json()) == 2
    utc_start = datetime.fromisoformat(payload["start_at"]).astimezone(ZoneInfo("UTC"))
    assert client.post("/api/appointments", headers=headers,
                       json={**payload, "start_at": utc_start.isoformat()}).status_code == 201
    assert client.post("/api/appointments", headers=headers, json=payload).status_code == 409
    assert client.put(f"{url}/{schedule_id}", headers=headers,
                      json=availability_payload(is_active=False)).status_code == 200
    assert client.get(slots_url, headers=headers).json() == []


def test_guest_booking_private_management_and_minimal_data(client, booking):
    headers, payload, slots_url = booking
    slots = client.get(slots_url).json()
    data = {"doctor_id": payload["doctor_id"], "start_at": payload["start_at"],
            "full_name": "Guest Patient", "phone": "+94771234567"}
    response = client.post("/api/guest/appointments", json=data)
    assert response.status_code == 201
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert not {"patient_id", "phone", "full_name", "guest_token_hash"} & body.keys()
    url = f"/api/guest/appointments/{body['id']}"
    token_headers = {"X-Booking-Token": body["management_token"]}
    assert client.get(url).status_code == 422
    assert client.get(url, headers={"X-Booking-Token": "x" * 43}).status_code == 401
    assert client.get(url, headers=token_headers).status_code == 200
    assert client.get(f"/api/appointments/{body['id']}").status_code == 401
    assert client.put(url + "/reschedule", headers=token_headers,
                      json={"start_at": slots[1]["start_at"]}).status_code == 200
    second = client.post("/api/guest/appointments", json=data).json()
    assert client.get(f"/api/guest/appointments/{second['id']}", headers=token_headers).status_code == 401
    assert client.put(url + "/cancel", headers=token_headers).json()["status"] == "cancelled"
    patient = client.get("/api/patients?query=Guest", headers=headers).json()["items"][0]
    assert patient["date_of_birth"] is None
    assert patient["gender"] == "not_specified"
    for extra in ({"reason": "Symptoms"}, {"patient_id": payload["patient_id"]},
                  {"diagnosis": "test"}, {"phone": "invalid"}):
        assert client.post("/api/guest/appointments", json={**data, **extra}).status_code == 422


def test_guest_conflict_does_not_leave_patient_record(client, booking):
    headers, payload, _ = booking
    data = {"doctor_id": payload["doctor_id"], "start_at": payload["start_at"],
            "full_name": "Concurrent Guest", "phone": "0771234567"}
    with ThreadPoolExecutor(max_workers=2) as executor:
        codes = list(executor.map(lambda _: client.post("/api/guest/appointments", json=data).status_code, range(2)))
    assert sorted(codes) == [201, 409]
    assert client.get("/api/patients?query=Concurrent", headers=headers).json()["total"] == 1


def test_optional_patient_accounts_are_isolated_from_staff(client, booking):
    _, payload, _ = booking
    credentials = {"username": "patient_one", "password": "PatientPassword123!"}
    created = client.post("/api/auth/register-patient", json=credentials)
    assert created.status_code == 201
    assert created.json()["role"] == "patient"
    assert client.post("/api/auth/register-patient", json={**credentials, "role": "administrator"}).status_code == 422
    assert client.post("/api/auth/register-patient", json=credentials).status_code == 409
    token = client.post("/api/auth/login", json=credentials).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/auth/me", headers=headers).status_code == 200
    assert client.get("/api/patients", headers=headers).status_code == 403
    assert client.post("/api/appointments", headers=headers, json=payload).status_code == 403
    response = client.post("/api/guest/appointments", headers=headers, json={
        "doctor_id": payload["doctor_id"], "start_at": payload["start_at"],
        "full_name": "Account Patient", "phone": "0771234567",
    })
    assert response.status_code == 201
    booking_id = response.json()["id"]
    assert client.get("/api/my/appointments", headers=headers).json()[0]["id"] == booking_id
    other = {"username": "patient_two", "password": "PatientPassword456!"}
    assert client.post("/api/auth/register-patient", json=other).status_code == 201
    other_token = client.post("/api/auth/login", json=other).json()["access_token"]
    other_headers = {"Authorization": f"Bearer {other_token}"}
    assert client.get("/api/my/appointments", headers=other_headers).json() == []
    assert client.put(f"/api/my/appointments/{booking_id}/cancel", headers=other_headers).status_code == 403
    assert client.put(f"/api/my/appointments/{booking_id}/cancel", headers=headers).status_code == 200


def test_public_doctors_hide_staff_fields(client):
    doctors = client.get("/api/doctors")
    assert doctors.status_code == 200
    assert set(doctors.json()[0]) == {"id", "display_name", "registration_number"}
    assert client.get(f"/api/doctors/{doctors.json()[0]['id']}").status_code == 200


def test_guest_token_is_hashed_and_expired_tokens_are_rejected(client, booking):
    from app.db.session import get_db
    from app.models import Appointment
    from app.services.security import hash_session_token
    from datetime import timezone

    _, payload, _ = booking
    response = client.post("/api/guest/appointments", json={
        "doctor_id": payload["doctor_id"], "start_at": payload["start_at"],
        "full_name": "Token Patient", "phone": "0771234567",
    }).json()
    dependency = client.app.dependency_overrides[get_db]()
    db = next(dependency)
    try:
        appointment = db.get(Appointment, response["id"])
        assert appointment.guest_token_hash == hash_session_token(response["management_token"])
        assert appointment.guest_token_hash != response["management_token"]
        appointment.start_at = datetime.now(timezone.utc) - timedelta(days=3)
        appointment.end_at = appointment.start_at + timedelta(minutes=15)
        db.commit()
    finally:
        dependency.close()
    assert client.get(f"/api/guest/appointments/{response['id']}", headers={
        "X-Booking-Token": response["management_token"],
    }).status_code == 401


def test_existing_schema_upgrade_is_repeatable_and_purge_is_explicit(client):
    from sqlalchemy import inspect, text
    from app.db.session import get_db
    from app.db.initialize import upgrade_booking_schema

    dependency = client.app.dependency_overrides[get_db]()
    db = next(dependency)
    try:
        engine = db.get_bind()
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE appointments ADD COLUMN reason VARCHAR(255)"))
            for column in ("presenting_complaint", "diagnosis", "clinical_notes", "treatment_plan"):
                connection.execute(text(f"ALTER TABLE visits ADD COLUMN {column} TEXT"))
            connection.execute(text("ALTER TABLE appointments DROP COLUMN guest_token_hash"))
            connection.execute(text("ALTER TABLE appointments DROP COLUMN booked_by_user_id"))
            connection.execute(text("ALTER TABLE patients ALTER COLUMN date_of_birth SET NOT NULL"))
        upgrade_booking_schema(engine)
        columns = {c["name"] for c in inspect(engine).get_columns("appointments")}
        assert {"guest_token_hash", "booked_by_user_id", "reason"} <= columns
        assert next(c for c in inspect(engine).get_columns("patients") if c["name"] == "date_of_birth")["nullable"]
        upgrade_booking_schema(engine, purge_clinical_data=True)
        upgrade_booking_schema(engine, purge_clinical_data=True)
        assert "reason" not in {c["name"] for c in inspect(engine).get_columns("appointments")}
        assert not {"diagnosis", "clinical_notes", "treatment_plan", "presenting_complaint"} & {
            c["name"] for c in inspect(engine).get_columns("visits")
        }
    finally:
        dependency.close()
