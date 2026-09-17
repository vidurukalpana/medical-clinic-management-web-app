from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone, time
from zoneinfo import ZoneInfo

import pytest

from app.db.session import get_db
from app.models import Appointment, Availability
from app.services import visits, appointments
from tests.test_doctor_scheduling import configured_password, login


@pytest.fixture
def opd(client, test_settings, monkeypatch):
    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2030, 1, 7, 8, tzinfo=ZoneInfo(test_settings.timezone)).astimezone(tz)

    monkeypatch.setattr(visits, "datetime", FixedDatetime)
    monkeypatch.setattr(appointments, "datetime", FixedDatetime)
    headers, _ = login(client, "admin", configured_password(test_settings.admin_password))
    doctors = client.get("/api/doctors", headers=headers).json()
    dependency = client.app.dependency_overrides[get_db]()
    db = next(dependency)
    try:
        for doctor in doctors:
            for weekday in (0, 1):
                db.add(Availability(
                    doctor_id=doctor["id"], weekday=weekday,
                    start_time=time(9), end_time=time(11),
                    slot_duration_minutes=15, is_active=True,
                ))
        db.commit()
    finally:
        dependency.close()
    patients = []
    for name in ("First Patient", "Second Patient", "Third Patient"):
        response = client.post("/api/patients", headers=headers, json={
            "full_name": name, "date_of_birth": "1990-01-01",
            "gender": "female", "phone": "0771234567",
        })
        assert response.status_code == 201
        patients.append(response.json()["id"])
    return headers, doctors, patients


def make_appointment(client, doctor_id, patient_id, days=0, status="scheduled"):
    dependency = client.app.dependency_overrides[get_db]()
    db = next(dependency)
    try:
        start = visits.datetime.now(timezone.utc) + timedelta(days=days)
        appointment = Appointment(
            doctor_id=doctor_id, patient_id=patient_id,
            start_at=start, end_at=start + timedelta(minutes=15), status=status,
        )
        db.add(appointment)
        db.commit()
        return appointment.id
    finally:
        dependency.close()


def walk_in(client, headers, doctor_id, patient_id):
    return client.post("/api/visits/walk-in", headers=headers, json={
        "doctor_id": doctor_id, "patient_id": patient_id,
    })


def test_check_in_consultation_and_appointment_sync(client, opd):
    headers, doctors, patients = opd
    doctor_id = doctors[0]["id"]
    appointment_id = make_appointment(client, doctor_id, patients[0])
    appointment_url = f"/api/appointments/{appointment_id}"
    response = client.post(appointment_url + "/check-in", headers=headers, json={})
    assert response.status_code == 201
    visit = response.json()
    assert visit["queue_number"] == 1
    assert visit["status"] == "waiting"
    assert visit["patient_id"] == patients[0]
    assert client.post(appointment_url + "/check-in", headers=headers, json={}).status_code == 409
    assert client.put(appointment_url + "/cancel", headers=headers).status_code == 409
    assert client.put(appointment_url + "/reschedule", headers=headers, json={
        "start_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
    }).status_code == 409
    url = f"/api/visits/{visit['id']}"
    assert client.patch(url, headers=headers, json={"status": "completed"}).status_code == 409
    assert client.patch(url, headers=headers, json={"status": "in_progress"}).status_code == 200
    response = client.patch(url, headers=headers, json={
        "status": "completed",
    })
    assert response.status_code == 200
    assert "diagnosis" not in client.get(url, headers=headers).json()
    assert client.get(appointment_url, headers=headers).json()["status"] == "completed"
    assert client.patch(url, headers=headers, json={"status": "in_progress"}).status_code == 409


def test_queue_numbers_walk_ins_cancellation_and_daily_reset(client, opd, monkeypatch, test_settings):
    headers, doctors, patients = opd
    doctor_id = doctors[0]["id"]
    first = walk_in(client, headers, doctor_id, patients[0])
    assert first.status_code == 201
    assert first.json()["appointment_id"] is not None
    assert "presenting_complaint" not in first.json()
    assert walk_in(client, headers, doctor_id, patients[0]).status_code == 409
    appointment_id = make_appointment(client, doctor_id, patients[1])
    second = client.post(f"/api/appointments/{appointment_id}/check-in", headers=headers, json={})
    assert second.json()["queue_number"] == 2
    assert client.patch(f"/api/visits/{second.json()['id']}", headers=headers,
                        json={"status": "cancelled"}).status_code == 200
    assert client.get(f"/api/appointments/{appointment_id}", headers=headers).json()["status"] == "cancelled"
    assert walk_in(client, headers, doctor_id, patients[1]).json()["queue_number"] == 3
    queue = client.get(f"/api/doctors/{doctor_id}/queue", headers=headers).json()
    assert [v["queue_number"] for v in queue] == [2, 1, 3]
    assert walk_in(client, headers, doctors[1]["id"], patients[2]).json()["queue_number"] == 1
    tomorrow = visits.clinic_today(test_settings.timezone) + timedelta(days=1)
    monkeypatch.setattr(visits, "clinic_today", lambda _: tomorrow)
    assert walk_in(client, headers, doctor_id, patients[0]).json()["queue_number"] == 1
    assert len(client.get(f"/api/doctors/{doctor_id}/queue", headers=headers).json()) == 1


def test_concurrent_queue_allocation_and_duplicate_check_in(client, opd):
    headers, doctors, patients = opd
    doctor_id = doctors[0]["id"]
    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(
            lambda patient: walk_in(client, headers, doctor_id, patient), patients[:2],
        ))
    assert [r.status_code for r in responses] == [201, 201]
    assert sorted(r.json()["queue_number"] for r in responses) == [1, 2]
    appointment_id = make_appointment(client, doctor_id, patients[2])
    with ThreadPoolExecutor(max_workers=2) as executor:
        codes = list(executor.map(lambda _: client.post(
            f"/api/appointments/{appointment_id}/check-in", headers=headers, json={},
        ).status_code, range(2)))
    assert sorted(codes) == [201, 409]


def test_invalid_check_in_and_validation(client, opd):
    headers, doctors, patients = opd
    doctor_id = doctors[0]["id"]
    for days, status, expected in ((1, "scheduled", 400), (-1, "scheduled", 400),
                                   (0, "cancelled", 409), (0, "no_show", 409)):
        appointment_id = make_appointment(client, doctor_id, patients[0], days, status)
        assert client.post(f"/api/appointments/{appointment_id}/check-in",
                           headers=headers, json={}).status_code == expected
    assert walk_in(client, headers, doctor_id, 99999).status_code == 404
    assert walk_in(client, headers, 99999, patients[0]).status_code == 404
    assert client.get("/api/visits/99999", headers=headers).status_code == 404
    first = walk_in(client, headers, doctor_id, patients[0]).json()
    for data in ({}, {"status": None}, {"status": "invalid"}, {"queue_number": 10},
                 {"clinical_notes": "x" * 20001}):
        assert client.patch(f"/api/visits/{first['id']}", headers=headers,
                            json=data).status_code == 422
    assert client.patch(f"/api/doctors/{doctor_id}", headers=headers,
                        json={"is_active": False}).status_code == 200
    assert walk_in(client, headers, doctor_id, patients[1]).status_code == 409


def test_visit_permissions(client, opd, test_settings):
    headers, doctors, patients = opd
    doctor_headers, body = login(client, "doctor1", configured_password(test_settings.doctor_one_password))
    own_id = body["user"]["doctor"]["id"]
    other_id = next(d["id"] for d in doctors if d["id"] != own_id)
    assert walk_in(client, {}, own_id, patients[0]).status_code == 401
    assert client.get(f"/api/doctors/{own_id}/queue").status_code == 401
    assert walk_in(client, doctor_headers, other_id, patients[0]).status_code == 403
    visit = walk_in(client, headers, other_id, patients[0]).json()
    assert client.patch(f"/api/visits/{visit['id']}", headers=doctor_headers,
                        json={"status": "in_progress"}).status_code == 403
    own = walk_in(client, doctor_headers, own_id, patients[0])
    assert own.status_code == 201
    assert client.patch(f"/api/visits/{own.json()['id']}", headers=doctor_headers,
                        json={"status": "in_progress"}).status_code == 200


def limit_slots(client, doctor_id, minutes=30):
    from sqlalchemy import select
    dependency = client.app.dependency_overrides[get_db]()
    db = next(dependency)
    try:
        schedule = db.scalar(select(Availability).where(
            Availability.doctor_id == doctor_id, Availability.weekday == 0,
        ))
        schedule.end_time = (datetime(2030, 1, 7, 9) + timedelta(minutes=minutes)).time()
        db.commit()
    finally:
        dependency.close()


def test_walk_in_uses_capacity_and_cancellation_releases_slot(client, opd):
    headers, doctors, patients = opd
    doctor_id = doctors[0]["id"]
    limit_slots(client, doctor_id)
    base = f"/api/doctors/{doctor_id}"
    slots = client.get(base + "/available-slots?day=2030-01-07", headers=headers).json()
    booked = client.post("/api/appointments", headers=headers, json={
        "doctor_id": doctor_id, "patient_id": patients[0], "start_at": slots[0]["start_at"],
    })
    assert booked.status_code == 201
    walk = walk_in(client, headers, doctor_id, patients[1])
    assert walk.status_code == 201
    reservation = client.get(f"/api/appointments/{walk.json()['appointment_id']}", headers=headers).json()
    assert datetime.fromisoformat(reservation["start_at"]) == datetime.fromisoformat(slots[1]["start_at"])
    assert client.get(base + "/booking-status?day=2030-01-07", headers=headers).json() == {
        "remaining_slots": 0, "is_fully_booked": True,
    }
    rejected = walk_in(client, headers, doctor_id, patients[2])
    assert rejected.status_code == 409
    assert "fully booked" in rejected.json()["detail"]
    assert client.post(f"/api/appointments/{booked.json()['id']}/check-in",
                       headers=headers, json={}).status_code == 201
    assert client.patch(f"/api/visits/{walk.json()['id']}", headers=headers,
                        json={"status": "cancelled"}).status_code == 200
    assert client.get(base + "/booking-status?day=2030-01-07", headers=headers).json()["remaining_slots"] == 1
    assert walk_in(client, headers, doctor_id, patients[2]).status_code == 201


def test_concurrent_walk_in_and_booking_compete_for_last_slot(client, opd):
    headers, doctors, patients = opd
    doctor_id = doctors[0]["id"]
    limit_slots(client, doctor_id, 15)
    def submit(kind):
        if kind == "walk":
            return walk_in(client, headers, doctor_id, patients[0]).status_code
        return client.post("/api/appointments", headers=headers, json={
            "doctor_id": doctor_id, "patient_id": patients[1],
            "start_at": "2030-01-07T09:00:00+05:30",
        }).status_code
    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(submit, ("walk", "book"))) == [201, 409]


def test_walk_in_rejected_without_working_time(client, opd):
    from app.models import DoctorUnavailability
    headers, doctors, patients = opd
    doctor_id = doctors[0]["id"]
    dependency = client.app.dependency_overrides[get_db]()
    db = next(dependency)
    try:
        db.add(DoctorUnavailability(
            doctor_id=doctor_id,
            start_at=datetime.fromisoformat("2030-01-07T09:00:00+05:30"),
            end_at=datetime.fromisoformat("2030-01-07T11:00:00+05:30"),
        ))
        db.commit()
    finally:
        dependency.close()
    assert walk_in(client, headers, doctor_id, patients[0]).status_code == 409
    assert client.get(f"/api/doctors/{doctor_id}/queue", headers=headers).json() == []


def test_twenty_booked_slots_reject_walk_ins_before_check_in(client, opd):
    from sqlalchemy import select
    headers, doctors, patients = opd
    doctor_id = doctors[0]["id"]
    dependency = client.app.dependency_overrides[get_db]()
    db = next(dependency)
    try:
        schedule = db.scalar(select(Availability).where(
            Availability.doctor_id == doctor_id, Availability.weekday == 0,
        ))
        schedule.slot_duration_minutes = 10
        schedule.end_time = time(12, 20)
        db.commit()
    finally:
        dependency.close()
    base = f"/api/doctors/{doctor_id}"
    slots = client.get(base + "/available-slots?day=2030-01-07", headers=headers).json()
    assert len(slots) == 20
    appointment_ids = []
    for slot in slots:
        response = client.post("/api/appointments", headers=headers, json={
            "doctor_id": doctor_id, "patient_id": patients[0],
            "start_at": slot["start_at"],
        })
        assert response.status_code == 201
        appointment_ids.append(response.json()["id"])
    assert client.get(base + "/queue", headers=headers).json() == []
    assert client.get(base + "/booking-status?day=2030-01-07", headers=headers).json() == {
        "remaining_slots": 0, "is_fully_booked": True,
    }
    assert walk_in(client, headers, doctor_id, patients[1]).status_code == 409
    assert client.get(base + "/queue", headers=headers).json() == []
    assert client.post(f"/api/appointments/{appointment_ids[0]}/check-in",
                       headers=headers, json={}).status_code == 201


def test_queue_uses_reserved_time_not_arrival_order(client, opd):
    headers, doctors, patients = opd
    doctor_id = doctors[0]["id"]
    booked = client.post("/api/appointments", headers=headers, json={
        "doctor_id": doctor_id, "patient_id": patients[0],
        "start_at": "2030-01-07T09:00:00+05:30",
    }).json()
    walk = walk_in(client, headers, doctor_id, patients[1]).json()
    checked_in = client.post(f"/api/appointments/{booked['id']}/check-in",
                             headers=headers, json={}).json()
    queue = client.get(f"/api/doctors/{doctor_id}/queue", headers=headers).json()
    assert [v["id"] for v in queue] == [checked_in["id"], walk["id"]]
    assert [v["queue_number"] for v in queue] == [2, 1]
    assert datetime.fromisoformat(queue[0]["start_at"]) < datetime.fromisoformat(queue[1]["start_at"])
    assert queue[0]["end_at"] is not None


def test_clinical_fields_are_rejected_and_other_doctor_cannot_read(client, opd, test_settings):
    headers, doctors, patients = opd
    doctor_headers, body = login(client, "doctor1", configured_password(test_settings.doctor_one_password))
    other_id = next(d["id"] for d in doctors if d["id"] != body["user"]["doctor"]["id"])
    response = walk_in(client, headers, other_id, patients[0])
    visit = response.json()
    for field in ("presenting_complaint", "diagnosis", "clinical_notes", "treatment_plan", "prescription"):
        assert client.patch(f"/api/visits/{visit['id']}", headers=headers, json={field: "text"}).status_code == 422
    assert client.get(f"/api/visits/{visit['id']}", headers=doctor_headers).status_code == 403
    assert client.get(f"/api/doctors/{other_id}/queue", headers=doctor_headers).status_code == 403
    assert client.get(f"/api/appointments/{visit['appointment_id']}", headers=doctor_headers).status_code == 403


def test_dashboard_daily_counts_queues_and_quick_actions(client, opd):
    headers, doctors, patients = opd
    doctor_id = doctors[0]["id"]
    booked = client.post("/api/appointments", headers=headers, json={
        "doctor_id": doctor_id, "patient_id": patients[0],
        "start_at": "2030-01-07T09:30:00+05:30",
    }).json()
    walked = walk_in(client, headers, doctor_id, patients[1]).json()
    response = client.get("/api/dashboard", headers=headers)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    dashboard = response.json()
    assert dashboard["day"] == "2030-01-07"
    assert dashboard["timezone"] == "Asia/Colombo"
    assert dashboard["summary"] == {
        "appointments": 2, "scheduled": 2, "waiting": 1, "in_progress": 0,
        "completed": 0, "cancelled": 0, "no_show": 0,
    }
    assert len(dashboard["doctor_queues"]) == 2
    queue = next(q for q in dashboard["doctor_queues"] if q["doctor_id"] == doctor_id)
    assert queue["patients"][0]["id"] == walked["id"]
    assert queue["patients"][0]["patient_name"] == "Second Patient"
    appointment = next(a for a in dashboard["appointments"] if a["id"] == booked["id"])
    check_in = next(a for a in appointment["actions"] if a["label"] == "Check in")
    assert client.request(check_in["method"], check_in["path"], headers=headers,
                          json=check_in["body"]).status_code == 201
    dashboard = client.get("/api/dashboard", headers=headers).json()
    queue = next(q for q in dashboard["doctor_queues"] if q["doctor_id"] == doctor_id)
    assert [v["patient_name"] for v in queue["patients"]] == ["Second Patient", "First Patient"]
    assert dashboard["summary"]["waiting"] == 2
    assert all(not a["actions"] for a in dashboard["appointments"])
    start = queue["patients"][0]["actions"][0]
    assert client.request(start["method"], start["path"], headers=headers, json=start["body"]).status_code == 200
    dashboard = client.get("/api/dashboard", headers=headers).json()
    assert dashboard["summary"]["waiting"] == 1
    assert dashboard["summary"]["in_progress"] == 1
    queue = next(q for q in dashboard["doctor_queues"] if q["doctor_id"] == doctor_id)
    complete = queue["patients"][0]["actions"][0]
    assert complete["label"] == "Complete"
    assert client.request(complete["method"], complete["path"], headers=headers, json=complete["body"]).status_code == 200
    dashboard = client.get("/api/dashboard", headers=headers).json()
    assert dashboard["summary"]["completed"] == 1
    assert dashboard["summary"]["in_progress"] == 0
    assert sum(len(q["patients"]) for q in dashboard["doctor_queues"]) == 1
    assert "phone" not in response.text
    assert "guest_token_hash" not in response.text
    assert "diagnosis" not in response.text


def test_dashboard_authorization_and_doctor_filter(client, opd, test_settings):
    headers, doctors, patients = opd
    doctor_headers, body = login(client, "doctor1", configured_password(test_settings.doctor_one_password))
    own_id = body["user"]["doctor"]["id"]
    other_id = next(d["id"] for d in doctors if d["id"] != own_id)
    walk_in(client, headers, own_id, patients[0])
    walk_in(client, headers, other_id, patients[1])
    assert client.get("/api/dashboard").status_code == 401
    own = client.get("/api/dashboard", headers=doctor_headers).json()
    assert [q["doctor_id"] for q in own["doctor_queues"]] == [own_id]
    assert {a["doctor_id"] for a in own["appointments"]} == {own_id}
    assert own["summary"]["waiting"] == 1
    assert "Second Patient" not in str(own)
    assert client.get(f"/api/dashboard?doctor_id={other_id}", headers=doctor_headers).status_code == 403
    filtered = client.get(f"/api/dashboard?doctor_id={other_id}", headers=headers).json()
    assert filtered["summary"]["appointments"] == 1
    assert [q["doctor_id"] for q in filtered["doctor_queues"]] == [other_id]
    assert client.get("/api/dashboard?doctor_id=99999", headers=headers).status_code == 404
    assert client.get("/api/dashboard?doctor_id=0", headers=headers).status_code == 422
    credentials = {"username": "dashboard_patient", "password": "PatientPassword123!"}
    assert client.post("/api/auth/register-patient", json=credentials).status_code == 201
    patient_token = client.post("/api/auth/login", json=credentials).json()["access_token"]
    assert client.get("/api/dashboard", headers={"Authorization": "Bearer " + patient_token}).status_code == 403


def test_dashboard_uses_clinic_midnight_and_excludes_terminal_visits(client, opd):
    headers, doctors, patients = opd
    dependency = client.app.dependency_overrides[get_db]()
    db = next(dependency)
    try:
        for value, status in (("2030-01-06T18:29:00+00:00", "scheduled"),
                              ("2030-01-06T18:30:00+00:00", "cancelled"),
                              ("2030-01-07T18:29:00+00:00", "no_show"),
                              ("2030-01-07T18:30:00+00:00", "scheduled")):
            start = datetime.fromisoformat(value)
            db.add(Appointment(doctor_id=doctors[0]["id"], patient_id=patients[0],
                               start_at=start, end_at=start + timedelta(minutes=1), status=status))
        db.commit()
    finally:
        dependency.close()
    dashboard = client.get("/api/dashboard", headers=headers).json()
    assert dashboard["summary"]["appointments"] == 2
    assert dashboard["summary"]["cancelled"] == 1
    assert dashboard["summary"]["no_show"] == 1
    assert dashboard["summary"]["scheduled"] == 0
    assert all(not a["actions"] for a in dashboard["appointments"])
    assert all(not q["patients"] for q in dashboard["doctor_queues"])


def test_dashboard_empty_day_and_inactive_doctor(client, opd):
    headers, doctors, _ = opd
    assert client.patch(f"/api/doctors/{doctors[0]['id']}", headers=headers,
                        json={"is_active": False}).status_code == 200
    dashboard = client.get("/api/dashboard", headers=headers).json()
    assert all(value == 0 for value in dashboard["summary"].values())
    assert dashboard["appointments"] == []
    inactive = next(q for q in dashboard["doctor_queues"] if q["doctor_id"] == doctors[0]["id"])
    assert inactive["is_active"] is False
    assert inactive["patients"] == []
