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
                           json=availability_payload(end_time="10:00:00", max_patients=3))
    assert response.status_code == 201
    patient = client.post("/api/patients", headers=headers, json={
        "full_name": "Booking Patient", "date_of_birth": "1990-01-01",
        "gender": "female", "phone": "0771234567",
    })
    assert patient.status_code == 201
    payload = {"doctor_id": doctor_id, "patient_id": patient.json()["id"],
               "start_at": f"{day}T09:00:00+05:30"}
    return headers, payload, f"/api/doctors/{doctor_id}/sessions?day={day}"


def change_session(client, headers, payload, **changes):
    url = f"/api/doctors/{payload['doctor_id']}/availability"
    schedule_id = client.get(url, headers=headers).json()[0]["id"]
    return client.put(f"{url}/{schedule_id}", headers=headers,
                      json=availability_payload(**{"end_time": "10:00:00", "max_patients": 3, **changes}))


def add_tuesday_session(client, headers, payload, max_patients=3):
    response = client.post(f"/api/doctors/{payload['doctor_id']}/availability", headers=headers,
                           json=availability_payload(weekday=1, end_time="10:00:00", max_patients=max_patients))
    assert response.status_code == 201
    start = datetime.fromisoformat(payload["start_at"]) + timedelta(days=1)
    return start.isoformat()


def remaining(client, sessions_url):
    return [session["remaining"] for session in client.get(sessions_url).json()]


def test_booking_numbers_and_cancellation(client, booking):
    headers, payload, sessions_url = booking
    sessions = client.get(sessions_url, headers=headers).json()
    assert [(s["max_patients"], s["remaining"]) for s in sessions] == [(3, 3)]
    first = client.post("/api/appointments", headers=headers, json=payload)
    assert first.status_code == 201
    appointment = first.json()
    assert "reason" not in appointment
    assert appointment["appointment_number"] == 1
    assert (appointment["start_at"], appointment["end_at"]) == (sessions[0]["start_at"], sessions[0]["end_at"])
    url = f"/api/appointments/{appointment['id']}"
    assert client.get(url, headers=headers).status_code == 200
    second = client.post("/api/appointments", headers=headers, json=payload).json()
    assert second["appointment_number"] == 2
    assert remaining(client, sessions_url) == [1]
    assert client.put(url + "/cancel", headers=headers).json()["status"] == "cancelled"
    assert client.put(url + "/cancel", headers=headers).status_code == 200
    assert remaining(client, sessions_url) == [2]
    # A cancelled number goes to the next booking.
    numbers = [client.post("/api/appointments", headers=headers, json=payload).json()["appointment_number"]
               for _ in range(2)]
    assert numbers == [1, 3]
    assert remaining(client, sessions_url) == [0]
    full = client.post("/api/appointments", headers=headers, json=payload)
    assert full.status_code == 409
    assert "fully booked" in full.json()["detail"]
    assert client.put(url + "/reschedule", headers=headers,
                      json={"start_at": payload["start_at"]}).status_code == 409


def test_rescheduling_moves_to_another_session(client, booking):
    headers, payload, sessions_url = booking
    tuesday = add_tuesday_session(client, headers, payload)
    first = client.post("/api/appointments", headers=headers, json=payload).json()
    second = client.post("/api/appointments", headers=headers, json=payload).json()
    url = f"/api/appointments/{second['id']}/reschedule"
    # Rescheduling into the same session keeps the number.
    same = client.put(url, headers=headers, json={"start_at": payload["start_at"]})
    assert same.status_code == 200
    assert same.json()["appointment_number"] == 2
    moved = client.put(url, headers=headers, json={"start_at": tuesday})
    assert moved.status_code == 200
    assert moved.json()["appointment_number"] == 1
    assert datetime.fromisoformat(moved.json()["start_at"]) == datetime.fromisoformat(tuesday)
    assert remaining(client, sessions_url) == [2]
    assert client.get(f"/api/appointments/{first['id']}", headers=headers).json()["appointment_number"] == 1


def test_unavailability_and_invalid_sessions(client, booking):
    headers, payload, sessions_url = booking
    start = datetime.fromisoformat(payload["start_at"])
    for offset in (10, 60):
        data = {**payload, "start_at": (start + timedelta(minutes=offset)).isoformat()}
        assert client.post("/api/appointments", headers=headers, json=data).status_code == 409
    # Time off in any part of a session closes the whole session.
    response = client.post(f"/api/doctors/{payload['doctor_id']}/unavailability",
                           headers=headers, json={
                               "start_at": (start + timedelta(minutes=10)).isoformat(),
                               "end_at": (start + timedelta(minutes=20)).isoformat(),
                           })
    assert response.status_code == 201
    assert client.get(sessions_url, headers=headers).json() == []
    assert client.post("/api/appointments", headers=headers, json=payload).status_code == 409
    assert client.post("/api/appointments", headers=headers,
                       json={**payload, "start_at": "2020-01-01T09:00:00+05:30"}).status_code == 400
    assert client.post("/api/appointments", headers=headers,
                       json={**payload, "start_at": "2030-01-01T09:00:00"}).status_code == 422
    assert client.post("/api/appointments", headers=headers,
                       json={**payload, "patient_id": 99999}).status_code == 404
    assert client.get("/api/appointments/99999", headers=headers).status_code == 404
    assert client.get("/api/doctors/99999/sessions?day=2030-01-01",
                      headers=headers).status_code == 404


def test_failed_reschedule_preserves_original_booking(client, booking):
    headers, payload, _ = booking
    tuesday = add_tuesday_session(client, headers, payload, max_patients=1)
    first = client.post("/api/appointments", headers=headers, json=payload).json()
    assert client.post("/api/appointments", headers=headers,
                       json={**payload, "start_at": tuesday}).status_code == 201
    url = f"/api/appointments/{first['id']}"
    assert client.put(url + "/reschedule", headers=headers,
                      json={"start_at": tuesday}).status_code == 409
    kept = client.get(url, headers=headers).json()
    assert (kept["start_at"], kept["appointment_number"]) == (first["start_at"], 1)


def test_concurrent_bookings_get_distinct_numbers_up_to_the_limit(client, booking):
    headers, payload, _ = booking
    def book(_):
        return client.post("/api/appointments", headers=headers, json=payload)
    with ThreadPoolExecutor(max_workers=4) as executor:
        responses = list(executor.map(book, range(4)))
    assert sorted(r.status_code for r in responses) == [201, 201, 201, 409]
    assert sorted(r.json()["appointment_number"] for r in responses if r.status_code == 201) == [1, 2, 3]


def test_permissions_and_inactive_doctor(client, booking, test_settings):
    headers, payload, sessions_url = booking
    assert client.get(sessions_url).status_code == 200
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
    assert client.get(sessions_url, headers=headers).json() == []
    assert client.post("/api/appointments", headers=headers, json=payload).status_code == 409


def test_session_changes_respect_booked_numbers(client, booking):
    headers, payload, sessions_url = booking
    created = [client.post("/api/appointments", headers=headers, json=payload).json() for _ in range(2)]
    assert change_session(client, headers, payload, max_patients=1).status_code == 409
    assert change_session(client, headers, payload, max_patients=2).status_code == 200
    assert remaining(client, sessions_url) == [0]
    assert client.post("/api/appointments", headers=headers, json=payload).status_code == 409
    # A new end time carries over to the session's bookings.
    assert change_session(client, headers, payload, max_patients=2, end_time="11:00:00").status_code == 200
    moved = client.get(f"/api/appointments/{created[0]['id']}", headers=headers).json()
    assert datetime.fromisoformat(moved["end_at"]) == datetime.fromisoformat(payload["start_at"]) + timedelta(hours=2)
    assert change_session(client, headers, payload, start_time="08:30:00").status_code == 409


def test_equivalent_timezone_books_the_same_session(client, booking):
    headers, payload, sessions_url = booking
    utc_start = datetime.fromisoformat(payload["start_at"]).astimezone(ZoneInfo("UTC"))
    created = client.post("/api/appointments", headers=headers,
                          json={**payload, "start_at": utc_start.isoformat()})
    assert created.status_code == 201
    assert client.post("/api/appointments", headers=headers, json=payload).json()["appointment_number"] == 2
    assert remaining(client, sessions_url) == [1]
    assert change_session(client, headers, payload, is_active=False).status_code == 409


def test_reserved_places_are_kept_from_online_booking(client, booking):
    headers, payload, sessions_url = booking
    assert change_session(client, headers, payload, reserved_places=1).status_code == 200
    session = client.get(sessions_url).json()[0]
    assert (session["remaining"], session["remaining_online"]) == (3, 2)
    guest = {"doctor_id": payload["doctor_id"], "start_at": payload["start_at"],
             "full_name": "Online Patient", "phone": "0771234567"}
    online = [client.post("/api/guest/appointments", json=guest) for _ in range(2)]
    assert [r.json()["appointment_number"] for r in online] == [1, 2]
    blocked = client.post("/api/guest/appointments", json=guest)
    assert blocked.status_code == 409
    assert "Online booking for this session is full" in blocked.json()["detail"]
    day = payload["start_at"][:10]
    status_url = f"/api/doctors/{payload['doctor_id']}/booking-status?day={day}"
    assert client.get(status_url).json() == {
        "remaining_places": 1, "remaining_online_places": 0, "is_fully_booked": False,
    }

    # Online bookings cannot move into a session whose online places are taken.
    tuesday = add_tuesday_session(client, headers, payload)
    moving = client.post("/api/guest/appointments", json={**guest, "start_at": tuesday}).json()
    assert client.put(f"/api/guest/appointments/{moving['id']}/reschedule",
                      headers={"X-Booking-Token": moving["management_token"]},
                      json={"start_at": payload["start_at"]}).status_code == 409
    # Reception can still use the kept place.
    staff = client.post("/api/appointments", headers=headers, json=payload)
    assert staff.status_code == 201
    assert staff.json()["appointment_number"] == 3
    assert client.get(status_url).json()["is_fully_booked"] is True


def test_guest_booking_private_management_and_minimal_data(client, booking):
    headers, payload, _ = booking
    data = {"doctor_id": payload["doctor_id"], "start_at": payload["start_at"],
            "full_name": "Guest Patient", "phone": "+94771234567"}
    response = client.post("/api/guest/appointments", json=data)
    assert response.status_code == 201
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert body["appointment_number"] == 1
    assert not {"patient_id", "phone", "full_name", "guest_token_hash"} & body.keys()
    url = f"/api/guest/appointments/{body['id']}"
    token_headers = {"X-Booking-Token": body["management_token"]}
    assert client.get(url).status_code == 422
    assert client.get(url, headers={"X-Booking-Token": "x" * 43}).status_code == 401
    assert client.get(url, headers=token_headers).status_code == 200
    assert client.get(f"/api/appointments/{body['id']}").status_code == 401
    tuesday = add_tuesday_session(client, headers, payload)
    moved = client.put(url + "/reschedule", headers=token_headers, json={"start_at": tuesday})
    assert moved.status_code == 200
    assert moved.json()["appointment_number"] == 1
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
    assert change_session(client, headers, payload, max_patients=1).status_code == 200
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
    assert set(doctors.json()[0]) == {
        "id", "display_name", "registration_number", "specialty", "qualifications",
        "languages", "bio", "consultation_fee", "weekly_sessions",
    }
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


def test_schema_upgrade_converts_legacy_unavailability_dates_and_patient_sex(client, test_settings):
    from sqlalchemy import inspect, text
    from app.db.session import get_db
    from app.db.initialize import upgrade_booking_schema

    dependency = client.app.dependency_overrides[get_db]()
    db = next(dependency)
    try:
        engine = db.get_bind()
        # Recreate the pre-period schema: one whole-day date per row and a required `sex` column.
        with engine.begin() as connection:
            connection.execute(text(
                "ALTER TABLE doctor_unavailability DROP CONSTRAINT ck_doctor_unavailability_time_order, "
                "DROP COLUMN start_at, DROP COLUMN end_at, ADD COLUMN unavailable_date DATE NOT NULL, "
                "ADD COLUMN created_at TIMESTAMP NOT NULL, ADD COLUMN updated_at TIMESTAMP NOT NULL, "
                "ADD CONSTRAINT uq_doctor_unavailability_doctor_date UNIQUE (doctor_id, unavailable_date)"
            ))
            connection.execute(text(
                "INSERT INTO doctor_unavailability (doctor_id, unavailable_date, reason, created_at, updated_at) "
                "VALUES (1, '2030-01-07', 'Leave', now(), now())"
            ))
            connection.execute(text("ALTER TABLE patients DROP COLUMN gender, ADD COLUMN sex VARCHAR(20) NOT NULL"))
            connection.execute(text(
                "INSERT INTO patients (medical_record_number, full_name, phone, sex, created_at, updated_at) "
                "VALUES ('MRN-LEGACY', 'Legacy Patient', '0771234567', 'F', now(), now())"
            ))
        upgrade_booking_schema(engine, timezone="Asia/Colombo")
        upgrade_booking_schema(engine, timezone="Asia/Colombo")

        with engine.connect() as connection:
            start_at, end_at = connection.execute(text(
                "SELECT start_at, end_at FROM doctor_unavailability WHERE reason = 'Leave'"
            )).one()
            gender = connection.execute(text(
                "SELECT gender FROM patients WHERE medical_record_number = 'MRN-LEGACY'"
            )).scalar_one()
        colombo = ZoneInfo("Asia/Colombo")
        assert start_at == datetime(2030, 1, 7, tzinfo=colombo)
        assert end_at == datetime(2030, 1, 8, tzinfo=colombo)
        assert gender == "FEMALE"
        assert {"start_at", "end_at"} <= {c["name"] for c in inspect(engine).get_columns("doctor_unavailability")}
    finally:
        dependency.close()

    # The upgraded tables accept writes from the current models.
    headers, _ = login(client, "admin", configured_password(test_settings.admin_password))
    blocked = client.post("/api/doctors/1/unavailability", headers=headers, json={
        "start_at": "2030-01-08T09:00:00+05:30", "end_at": "2030-01-08T12:00:00+05:30",
    })
    assert blocked.status_code == 201
    periods = client.get("/api/doctors/1/unavailability", headers=headers).json()
    assert [(datetime.fromisoformat(p["start_at"]), p["reason"]) for p in periods] == [
        (datetime(2030, 1, 7, tzinfo=ZoneInfo("Asia/Colombo")), "Leave"),
        (datetime(2030, 1, 8, 9, tzinfo=ZoneInfo("Asia/Colombo")), None),
    ]
    patient = client.post("/api/patients", headers=headers, json={"full_name": "New Patient", "phone": "0777654321"})
    assert patient.status_code == 201
    legacy = client.get("/api/patients", headers=headers, params={"query": "MRN-LEGACY"}).json()["items"]
    assert legacy[0]["gender"] == "female"


def test_schema_upgrade_moves_slot_bookings_into_numbered_sessions(client, booking, test_settings):
    from sqlalchemy import text
    from app.db.session import get_db
    from app.db.initialize import upgrade_booking_schema

    headers, payload, sessions_url = booking
    session_start = datetime.fromisoformat(payload["start_at"])
    dependency = client.app.dependency_overrides[get_db]()
    db = next(dependency)
    try:
        engine = db.get_bind()
        # Recreate the slot schema: 15-minute slots and one booking per start time.
        with engine.begin() as connection:
            connection.execute(text(
                "ALTER TABLE availability DROP COLUMN max_patients, "
                "ADD COLUMN slot_duration_minutes INTEGER NOT NULL DEFAULT 15"
            ))
            connection.execute(text("ALTER TABLE appointments DROP COLUMN appointment_number, DROP COLUMN checkin_code"))
            connection.execute(text(
                "CREATE UNIQUE INDEX uq_appointment_doctor_start ON appointments (doctor_id, start_at) "
                "WHERE status <> 'cancelled'"
            ))
            for minutes, status in ((30, "scheduled"), (0, "cancelled"), (15, "scheduled"), (0, "scheduled")):
                start = session_start + timedelta(minutes=minutes)
                connection.execute(text(
                    "INSERT INTO appointments (doctor_id, patient_id, start_at, end_at, status) "
                    "VALUES (:doctor, :patient, :start, :end, :status)"
                ), {"doctor": payload["doctor_id"], "patient": payload["patient_id"],
                    "start": start, "end": start + timedelta(minutes=15), "status": status})
        upgrade_booking_schema(engine, timezone=test_settings.timezone)
        upgrade_booking_schema(engine, timezone=test_settings.timezone)
        with engine.connect() as connection:
            rows = connection.execute(text(
                "SELECT start_at, end_at, appointment_number, status FROM appointments ORDER BY id"
            )).all()
            codes = connection.execute(text("SELECT checkin_code FROM appointments")).scalars().all()
            max_patients = connection.execute(text("SELECT max_patients FROM availability")).scalar_one()
    finally:
        dependency.close()

    assert len(set(codes)) == len(codes) == 4 and all(len(code) == 10 for code in codes)
    # 09:00-10:00 in 15-minute slots held four patients.
    assert max_patients == 4
    assert [(row.start_at, row.appointment_number, row.status) for row in rows] == [
        (session_start, 3, "scheduled"), (session_start, 4, "cancelled"),
        (session_start, 2, "scheduled"), (session_start, 1, "scheduled"),
    ]
    assert {row.end_at for row in rows if row.status == "scheduled"} == {session_start + timedelta(hours=1)}
    assert remaining(client, sessions_url) == [1]
    added = client.post("/api/appointments", headers=headers, json=payload)
    assert added.json()["appointment_number"] == 4


def test_doctor_public_profile_and_weekly_sessions(client, booking, test_settings):
    headers, payload, _ = booking
    doctor_url = f"/api/doctors/{payload['doctor_id']}"
    updated = client.patch(doctor_url, headers=headers, json={
        "specialty": " Consultant Paediatrician ", "qualifications": "MBBS (Colombo), MD (Paediatrics)",
        "languages": "Sinhala, English", "bio": "", "consultation_fee": 2500,
    })
    assert updated.status_code == 200
    assert (updated.json()["specialty"], updated.json()["bio"]) == ("Consultant Paediatrician", None)
    assert client.patch(doctor_url, headers=headers, json={"consultation_fee": -1}).status_code == 422
    # A paused session is not advertised.
    assert client.post(f"{doctor_url}/availability", headers=headers, json=availability_payload(
        weekday=2, start_time="17:00:00", end_time="19:00:00", is_active=False,
    )).status_code == 201
    profile = client.get(doctor_url).json()
    assert profile["consultation_fee"] == 2500
    assert profile["weekly_sessions"] == [{"weekday": 0, "start_time": "09:00:00", "end_time": "10:00:00"}]
    assert "phone" not in profile

    doctor_headers, body = login(client, "doctor1", configured_password(test_settings.doctor_one_password))
    own = client.patch("/api/doctors/me", headers=doctor_headers, json={"specialty": "General Practitioner"})
    assert own.status_code == 200
    assert own.json()["specialty"] == "General Practitioner"


def test_demo_data_is_repeatable(client, test_settings):
    from app.db.demo_data import DEMO_DOCTORS, seed_demo_data
    from app.db.session import get_db
    from app.models import Appointment, Patient

    dependency = client.app.dependency_overrides[get_db]()
    db = next(dependency)
    try:
        passwords = {demo.username: f"{demo.username}-password" for demo in DEMO_DOCTORS}
        assert seed_demo_data(db, test_settings.timezone, passwords) == [demo.username for demo in DEMO_DOCTORS]
        counts = (db.query(Patient).count(), db.query(Appointment).count())
        assert seed_demo_data(db, test_settings.timezone, passwords) == []
        assert (db.query(Patient).count(), db.query(Appointment).count()) == counts
    finally:
        dependency.close()
    doctors = client.get("/api/doctors").json()
    assert len(doctors) == 2 + len(DEMO_DOCTORS)
    assert all(doctor["specialty"] for doctor in doctors)
    login(client, DEMO_DOCTORS[0].username, passwords[DEMO_DOCTORS[0].username])
