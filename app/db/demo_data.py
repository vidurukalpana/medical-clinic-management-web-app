"""Fictional demo doctors, sessions, patients and bookings for local development.

Run with `python -m app.db.demo_data`. It is safe to run repeatedly: records that
already exist are left as they are. Demo doctor passwords come from
CLINIC_DEMO_DOCTOR_PASSWORDS. Never run it against a real clinic database.
"""

import random
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Availability, Doctor, Patient, PatientGender, User, UserRole
from app.schemas.appointment import AppointmentCreate
from app.schemas.patient import PatientCreate
from app.services import appointments, visits
from app.services.doctors import list_doctors
from app.services.patients import create_patient
from app.services.security import hash_password

# Demo patients are recognised by this phone prefix.
DEMO_PHONE_PREFIX = "070 000 0"


@dataclass(frozen=True)
class DemoDoctor:
    username: str
    display_name: str
    registration_number: str
    specialty: str
    qualifications: str
    languages: str
    bio: str
    consultation_fee: int
    # (weekday, start hour, end hour); Monday is 0.
    sessions: tuple[tuple[int, int, int], ...] = ()
    max_patients: int = 20
    reserved_places: int = 0


# Profiles for the two doctors created at startup, filled in only where empty.
SEEDED_PROFILES = {
    "DOC-001": DemoDoctor(
        "", "", "DOC-001", "General Practitioner", "MBBS (Colombo)", "Sinhala, English",
        "Family doctor for everyday illnesses, check-ups and follow-up care.", 1500,
    ),
    "DOC-002": DemoDoctor(
        "", "", "DOC-002", "Consultant Physician", "MBBS (Peradeniya), MD (Medicine)",
        "Sinhala, Tamil, English", "Diabetes, blood pressure and long-term conditions in adults.", 2500,
    ),
}

DEMO_DOCTORS = (
    DemoDoctor(
        "demo.ayesha", "Dr. Ayesha Fernando", "DEMO-101", "Consultant Paediatrician",
        "MBBS (Colombo), MD (Paediatrics), DCH", "Sinhala, English",
        "Care for babies, children and teenagers, including vaccinations and growth checks.", 2500,
        sessions=((0, 17, 20), (2, 17, 20)), max_patients=20, reserved_places=4,
    ),
    DemoDoctor(
        "demo.ruwan", "Dr. Ruwan Jayasinghe", "DEMO-102", "Consultant Cardiologist",
        "MBBS (Peradeniya), MD (Medicine), MRCP (UK)", "Sinhala, English",
        "Heart health, chest pain, palpitations and follow-up after heart treatment.", 3500,
        sessions=((1, 16, 19), (3, 16, 19)), max_patients=15, reserved_places=3,
    ),
    DemoDoctor(
        "demo.priya", "Dr. Priya Raman", "DEMO-103", "Consultant Dermatologist",
        "MBBS (Jaffna), MD (Dermatology)", "Tamil, English",
        "Skin, hair and nail conditions, including eczema, acne and allergies.", 3000,
        sessions=((2, 9, 12), (4, 14, 17)), max_patients=18, reserved_places=3,
    ),
    DemoDoctor(
        "demo.kasun", "Dr. Kasun Wickramasinghe", "DEMO-104", "General Practitioner",
        "MBBS (Kelaniya), DFM", "Sinhala, English",
        "Morning clinic for everyday illnesses, medical certificates and check-ups.", 1500,
        sessions=tuple((weekday, 8, 11) for weekday in range(5)), max_patients=25, reserved_places=5,
    ),
)

DEMO_PATIENTS = (
    ("Nimal Perera", PatientGender.MALE), ("Kumari Silva", PatientGender.FEMALE),
    ("Tharindu Bandara", PatientGender.MALE), ("Fathima Rizwan", PatientGender.FEMALE),
    ("Saman Kumara", PatientGender.MALE), ("Dilini Wijesekara", PatientGender.FEMALE),
    ("Arjun Selvarajah", PatientGender.MALE), ("Chamari Gunawardena", PatientGender.FEMALE),
    ("Mohamed Imran", PatientGender.MALE), ("Ishara Madushani", PatientGender.FEMALE),
    ("Ranjith Senanayake", PatientGender.MALE), ("Lakshmi Nadarajah", PatientGender.FEMALE),
)


def seed_demo_data(db: Session, clinic_timezone: str, passwords: Mapping[str, str]) -> list[str]:
    """Add the demo records; returns the username of each new doctor account."""
    _fill_seeded_profiles(db)
    accounts = _create_demo_doctors(db, passwords)
    db.commit()
    if db.scalar(select(Patient.id).where(Patient.phone.startswith(DEMO_PHONE_PREFIX))) is None:
        patients = [
            create_patient(db, PatientCreate(
                full_name=name, gender=gender, phone=f"{DEMO_PHONE_PREFIX}{index:03d}",
                date_of_birth=date(1950 + index * 5, 1 + index, 10 + index),
            ))
            for index, (name, gender) in enumerate(DEMO_PATIENTS)
        ]
        _book_demo_patients(db, patients, clinic_timezone)
    return accounts


def _fill_seeded_profiles(db: Session) -> None:
    for doctor in db.scalars(select(Doctor).where(Doctor.registration_number.in_(SEEDED_PROFILES))):
        profile = SEEDED_PROFILES[doctor.registration_number]
        for field in ("specialty", "qualifications", "languages", "bio", "consultation_fee"):
            if getattr(doctor, field) is None:
                setattr(doctor, field, getattr(profile, field))


def _create_demo_doctors(db: Session, passwords: Mapping[str, str]) -> list[str]:
    accounts = []
    for demo in DEMO_DOCTORS:
        if db.scalar(select(Doctor.id).where(Doctor.registration_number == demo.registration_number)):
            continue
        if db.scalar(select(User.id).where(User.username == demo.username)):
            continue
        password = passwords.get(demo.username)
        if not password:
            raise RuntimeError(
                f"CLINIC_DEMO_DOCTOR_PASSWORDS must include a password for '{demo.username}'."
            )
        user = User(username=demo.username, password_hash=hash_password(password),
                    role=UserRole.DOCTOR, is_active=True)
        doctor = Doctor(
            user=user, display_name=demo.display_name, registration_number=demo.registration_number,
            specialty=demo.specialty, qualifications=demo.qualifications, languages=demo.languages,
            bio=demo.bio, consultation_fee=demo.consultation_fee, is_active=True,
        )
        doctor.availability = [
            Availability(weekday=weekday, start_time=time(start), end_time=time(end),
                         max_patients=demo.max_patients, reserved_places=demo.reserved_places,
                         is_active=True)
            for weekday, start, end in demo.sessions
        ]
        db.add(doctor)
        accounts.append(demo.username)
    return accounts


def _book_demo_patients(db: Session, patients: list[Patient], clinic_timezone: str) -> None:
    """Book a few patients into each open session today and over the next two days."""
    chooser = random.Random(7)
    today = datetime.now(ZoneInfo(clinic_timezone)).date()
    for doctor in list_doctors(db):
        for day in (today + timedelta(days=offset) for offset in range(3)):
            for session in appointments.booking_sessions(db, doctor, day, clinic_timezone):
                booked = []
                for patient in chooser.sample(patients, min(len(patients), session.remaining, chooser.randint(3, 7))):
                    booked.append(appointments.create_appointment(db, doctor, AppointmentCreate(
                        doctor_id=doctor.id, patient_id=patient.id, start_at=session.start_at,
                    ), clinic_timezone))
                    db.commit()
                if day == today and session.start_at <= datetime.now(session.start_at.tzinfo):
                    _start_session(db, doctor, booked, clinic_timezone)


def _start_session(db: Session, doctor: Doctor, booked: list, clinic_timezone: str) -> None:
    """For a session already running, check everyone in and put the doctor partway through."""
    queued = []
    for appointment in booked:
        queued.append(visits.check_in(db, doctor, appointment, clinic_timezone))
        db.flush()  # The next check-in numbers itself from the saved visits.
    for visit, status in zip(queued, ("completed", "completed", "in_progress")):
        visit.status = status
        if status == "completed":
            visit.appointment.status = "completed"
    db.commit()


if __name__ == "__main__":
    from app.core.config import get_settings
    from app.db.session import engine

    settings = get_settings()
    passwords = {username: secret.get_secret_value()
                 for username, secret in settings.demo_doctor_passwords.items()}
    with Session(engine) as session:
        created = seed_demo_data(session, settings.timezone, passwords)
    print("Demo data is ready.")
    for username in created:
        print(f"  New doctor account: {username}")
