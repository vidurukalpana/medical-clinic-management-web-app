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
               "start_at": f"{day}T09:00:00+05:30", "reason": " Checkup "}
    return headers, payload, f"/api/doctors/{doctor_id}/available-slots?day={day}"


def test_booking_rescheduling_and_cancellation(client, booking):
    headers, payload, slots_url = booking
    slots = client.get(slots_url, headers=headers).json()
    assert len(slots) == 4
    created = client.post("/api/appointments", headers=headers, json=payload)
    assert created.status_code == 201
    appointment = created.json()
    url = f"/api/appointments/{appointment['id']}"
    assert appointment["reason"] == "Checkup"
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
    assert client.get(slots_url).status_code == 401
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
