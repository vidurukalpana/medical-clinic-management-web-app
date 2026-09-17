from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db.session import get_db
from app.models import Appointment, User
from tests.test_appointments import booking  # noqa: F401 - shared pytest fixture
from tests.test_doctor_scheduling import availability_payload, configured_password, login


def db_change(client, change):
    dependency = client.app.dependency_overrides[get_db]()
    db = next(dependency)
    try:
        result = change(db)
        db.commit()
        return result
    finally:
        dependency.close()


def staff(client, settings, username="admin"):
    password = settings.admin_password if username == "admin" else settings.doctor_two_password
    return login(client, username, configured_password(password))[0]


def test_no_show_lifecycle_and_permissions(client, booking, test_settings):
    headers, payload, _ = booking
    item = client.post("/api/appointments", headers=headers, json=payload).json()
    url = f"/api/appointments/{item['id']}/no-show"
    assert client.put(url).status_code == 401
    assert client.put(url, headers=staff(client, test_settings, "doctor2")).status_code == 403
    assert client.put(url, headers=headers).status_code == 409

    def expire(db):
        appointment = db.get(Appointment, item["id"])
        appointment.start_at = datetime.now(timezone.utc) - timedelta(hours=1)
        appointment.end_at = appointment.start_at + timedelta(minutes=15)
    db_change(client, expire)
    assert client.put(url, headers=headers).json()["status"] == "no_show"
    assert client.put(url, headers=headers).status_code == 200
    assert client.put(url.replace("no-show", "cancel"), headers=headers).status_code == 409
    assert client.post(url.replace("no-show", "check-in"), headers=headers, json={}).status_code == 409
    assert client.get("/api/dashboard", headers=headers).json()["summary"]["no_show"] == 1


def test_no_show_rejects_cancelled_and_checked_in(client, booking):
    from app.models import Visit
    headers, payload, _ = booking
    item = client.post("/api/appointments", headers=headers, json=payload).json()
    url = f"/api/appointments/{item['id']}"
    assert client.put(url + "/cancel", headers=headers).status_code == 200
    assert client.put(url + "/no-show", headers=headers).status_code == 409
    def checked_in(db):
        appointment = db.get(Appointment, item["id"])
        appointment.status = "scheduled"
        appointment.start_at = datetime.now(timezone.utc) - timedelta(hours=1)
        appointment.end_at = appointment.start_at + timedelta(minutes=15)
        db.add(Visit(appointment_id=appointment.id, doctor_id=appointment.doctor_id,
                     patient_id=appointment.patient_id, visit_date=appointment.start_at.date(),
                     queue_number=1, status="waiting"))
    db_change(client, checked_in)
    assert client.put(url + "/no-show", headers=headers).status_code == 409


def test_appointment_filters_pagination_and_scope(client, booking, test_settings):
    headers, payload, slots_url = booking
    slots = client.get(slots_url).json()
    for slot in slots[:2]:
        assert client.post("/api/appointments", headers=headers,
                           json={**payload, "start_at": slot["start_at"]}).status_code == 201
    day = payload["start_at"][:10]
    params = {"doctor_id": payload["doctor_id"], "patient_id": payload["patient_id"],
              "date_from": day, "date_to": day, "status": "scheduled", "limit": 1}
    response = client.get("/api/appointments", headers=headers, params=params)
    assert response.headers["cache-control"] == "no-store"
    page = response.json()
    assert page["total"] == 2 and len(page["items"]) == 1
    second = client.get("/api/appointments", headers=headers, params={**params, "offset": 1}).json()
    assert second["items"][0]["id"] != page["items"][0]["id"]
    assert client.get("/api/appointments", headers=headers, params={**params, "status": "cancelled"}).json()["total"] == 0
    other = staff(client, test_settings, "doctor2")
    assert client.get("/api/appointments", headers=other).json()["total"] == 0
    assert client.get("/api/appointments", headers=other, params=params).status_code == 403
    assert client.get("/api/appointments").status_code == 401
    assert client.get("/api/appointments?date_from=2030-02-01&date_to=2030-01-01", headers=headers).status_code == 400
    assert client.get("/api/appointments?status=invalid", headers=headers).status_code == 422
    assert client.get("/api/appointments?limit=101", headers=headers).status_code == 422
    assert db_change(client, lambda db: db.get(Appointment, page["items"][0]["id"]).booked_by_user_id) is not None


def test_schedule_changes_protect_bookings(client, booking):
    headers, payload, _ = booking
    item = client.post("/api/appointments", headers=headers, json=payload).json()
    base = f"/api/doctors/{payload['doctor_id']}"
    schedule = client.get(base + "/availability", headers=headers).json()[0]
    url = f"{base}/availability/{schedule['id']}"
    for data in (availability_payload(is_active=False),
                 availability_payload(start_time="09:15:00", end_time="10:00:00"),
                 availability_payload(weekday=1)):
        assert client.put(url, headers=headers, json=data).status_code == 409
    assert client.delete(url, headers=headers).status_code == 409
    assert client.get(base + "/availability", headers=headers).json()[0] == schedule
    block = {"start_at": item["start_at"], "end_at": item["end_at"]}
    assert client.post(base + "/unavailability", headers=headers, json=block).status_code == 409
    start = datetime.fromisoformat(item["end_at"])
    free = {"start_at": start.isoformat(), "end_at": (start + timedelta(minutes=15)).isoformat()}
    response = client.post(base + "/unavailability", headers=headers, json=free)
    assert response.status_code == 201
    block_url = f"{base}/unavailability/{response.json()['id']}"
    assert client.put(block_url, headers=headers, json=block).status_code == 409
    assert client.get(base + "/unavailability", headers=headers).json()[0]["id"] == response.json()["id"]
    assert client.put(f"/api/appointments/{item['id']}/cancel", headers=headers).status_code == 200
    assert client.delete(url, headers=headers).status_code == 204
    assert client.put(block_url, headers=headers, json=block).status_code == 200


def test_booking_and_block_are_serialized(client, booking):
    headers, payload, _ = booking
    start = datetime.fromisoformat(payload["start_at"])
    def request(kind):
        if kind == "book":
            return client.post("/api/appointments", headers=headers, json=payload).status_code
        return client.post(f"/api/doctors/{payload['doctor_id']}/unavailability", headers=headers,
                           json={"start_at": start.isoformat(),
                                 "end_at": (start + timedelta(minutes=15)).isoformat()}).status_code
    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(request, ["book", "block"])) == [201, 409]


def test_account_creation_roles_and_session_revocation(client, test_settings):
    headers = staff(client, test_settings)
    data = {"username": "NewDoctor", "password": "NewDoctorPassword123!", "role": "doctor",
            "doctor": {"display_name": "New Doctor", "registration_number": "NEW-001"}}
    response = client.post("/api/admin/users", headers=headers, json=data)
    assert response.status_code == 201
    account = response.json()
    assert account["username"] == "newdoctor" and account["doctor"]["user_id"] == account["id"]
    assert "password_hash" not in account
    assert client.post("/api/admin/users", headers=headers, json=data).status_code == 409
    assert client.post("/api/admin/users", headers=headers, json={**data, "username": "another"}).status_code == 409
    token, _ = login(client, "newdoctor", data["password"])
    assert client.get("/api/admin/users", headers=token).status_code == 403
    url = f"/api/admin/users/{account['id']}"
    assert client.patch(url, headers=headers, json={"is_active": False}).status_code == 200
    assert client.get("/api/auth/me", headers=token).status_code == 401
    assert client.patch(url, headers=headers, json={"is_active": True}).status_code == 200
    assert client.get("/api/auth/me", headers=token).status_code == 401
    token, _ = login(client, "newdoctor", data["password"])
    result = client.patch(url, headers=headers, json={"role": "patient"})
    assert result.status_code == 200 and result.json()["doctor"]["is_active"] is False
    assert client.get("/api/auth/me", headers=token).status_code == 401
    assert account["doctor"]["id"] not in [d["id"] for d in client.get("/api/doctors").json()]
    assert client.patch(url, headers=headers, json={"role": "doctor"}).json()["doctor"]["id"] == account["doctor"]["id"]
    assert client.get("/api/admin/users?role=doctor&limit=1", headers=headers).json()["total"] == 3
    assert client.get(url, headers=headers).status_code == 200
    assert client.patch(url, headers=headers, json={"role": None}).status_code == 422
    assert client.patch(url, headers=headers, json={}).status_code == 422
    assert client.get("/api/admin/users/999999", headers=headers).status_code == 404


def test_last_admin_and_role_profile_requirements(client, test_settings):
    headers = staff(client, test_settings)
    admin = client.get("/api/auth/me", headers=headers).json()
    url = f"/api/admin/users/{admin['id']}"
    assert client.patch(url, headers=headers, json={"is_active": False}).status_code == 409
    assert client.patch(url, headers=headers, json={"role": "patient"}).status_code == 409
    data = {"username": "second_admin", "password": "SecondAdminPassword123!", "role": "administrator"}
    second = client.post("/api/admin/users", headers=headers, json=data)
    assert second.status_code == 201
    second_url = f"/api/admin/users/{second.json()['id']}"
    assert client.patch(second_url, headers=headers, json={"role": "doctor"}).status_code == 409
    assert client.patch(second_url, headers=headers, json={
        "role": "doctor", "doctor": {"display_name": "Promoted Doctor", "registration_number": "PRO-001"},
    }).status_code == 200
    assert client.patch(second_url, headers=headers, json={"role": "administrator"}).status_code == 200
    assert client.patch(url, headers=headers, json={"role": "patient"}).status_code == 200
    assert client.get("/api/auth/me", headers=headers).status_code == 401
    # Restart seeding must respect deliberate role changes to initial accounts.
    from app.db.seed import seed_initial_accounts
    db_change(client, lambda db: seed_initial_accounts(db, test_settings))
    assert db_change(client, lambda db: db.scalar(select(User).where(User.id == admin["id"])).role) == "patient"


def test_concurrent_last_admin_changes_keep_one_admin(client, test_settings):
    headers = staff(client, test_settings)
    admin_id = client.get("/api/auth/me", headers=headers).json()["id"]
    account = client.post("/api/admin/users", headers=headers, json={
        "username": "backup_admin", "password": "BackupAdminPassword123!", "role": "administrator",
    }).json()
    backup, _ = login(client, "backup_admin", "BackupAdminPassword123!")
    def disable(item):
        user_id, auth = item
        return client.patch(f"/api/admin/users/{user_id}", headers=auth,
                            json={"is_active": False}).status_code
    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(disable, [(admin_id, headers), (account["id"], backup)])) == [200, 409]


def test_patient_cannot_use_staff_workflows(client, test_settings):
    data = {"username": "ordinary_patient", "password": "PatientPassword123!"}
    assert client.post("/api/auth/register-patient", json=data).status_code == 201
    headers, _ = login(client, data["username"], data["password"])
    assert client.get("/api/appointments", headers=headers).status_code == 403
    assert client.get("/api/admin/users", headers=headers).status_code == 403
    assert client.post("/api/admin/users", headers=headers, json={**data, "role": "administrator"}).status_code == 403
    assert client.patch("/api/admin/users/1", headers=headers, json={"role": "administrator"}).status_code == 403
    assert client.put("/api/appointments/1/no-show", headers=headers).status_code == 403


def test_appointment_date_filters_use_clinic_midnight(client, booking):
    headers, payload, _ = booking
    item = client.post("/api/appointments", headers=headers, json=payload).json()
    def midnight(db):
        appointment = db.get(Appointment, item["id"])
        appointment.start_at = datetime.fromisoformat("2030-01-06T18:30:00+00:00")
        appointment.end_at = appointment.start_at + timedelta(minutes=15)
    db_change(client, midnight)
    for day, total in (("2030-01-06", 0), ("2030-01-07", 1), ("2030-01-08", 0)):
        assert client.get("/api/appointments", headers=headers, params={
            "date_from": day, "date_to": day,
        }).json()["total"] == total


def test_concurrent_booking_and_availability_delete(client, booking):
    headers, payload, _ = booking
    url = f"/api/doctors/{payload['doctor_id']}/availability"
    period = client.get(url, headers=headers).json()[0]
    def request(kind):
        if kind == "book":
            return client.post("/api/appointments", headers=headers, json=payload).status_code
        return client.delete(f"{url}/{period['id']}", headers=headers).status_code
    with ThreadPoolExecutor(max_workers=2) as executor:
        codes = list(executor.map(request, ["book", "delete"]))
    assert codes in ([201, 409], [409, 204])


def test_demoted_doctor_cannot_have_profile_reactivated(client, test_settings):
    headers = staff(client, test_settings)
    doctor = client.get("/api/admin/doctors", headers=headers).json()[0]
    assert client.patch(f"/api/admin/users/{doctor['user_id']}", headers=headers,
                        json={"role": "patient"}).status_code == 200
    assert client.patch(f"/api/doctors/{doctor['id']}", headers=headers,
                        json={"is_active": True}).status_code == 409
    from app.db.seed import seed_initial_accounts
    db_change(client, lambda db: seed_initial_accounts(db, test_settings))
    assert client.get(f"/api/admin/users/{doctor['user_id']}", headers=headers).json()["role"] == "patient"
