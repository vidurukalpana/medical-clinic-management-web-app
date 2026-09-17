from datetime import date, datetime, timedelta, timezone
from secrets import compare_digest
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, Query, Response, status
from sqlalchemy import select

from app.core.config import Settings, get_settings
from app.dependencies import AuthenticatedUser, CurrentUser, DatabaseSession, OptionalUser
from app.errors import AuthenticationRequiredError, ForbiddenError
from app.errors.appointments import save_appointment
from app.models import Appointment, Doctor, User, UserRole
from app.schemas.appointment import (
    AppointmentPage, AppointmentCreate, AppointmentRead, AppointmentReschedule, AvailableSlot, BookingStatus,
    GuestBookingConfirmation, GuestBookingCreate, GuestBookingRead,
)
from app.schemas.patient import PatientCreate
from app.services import appointments
from app.services.patients import create_patient
from app.services.security import create_session_token, hash_session_token

router = APIRouter(tags=["appointments"])
AppSettings = Annotated[Settings, Depends(get_settings)]


def require_booking_manager(doctor: Doctor, user: User) -> None:
    if user.role != UserRole.ADMINISTRATOR and doctor.user_id != user.id:
        raise ForbiddenError("You can manage only your own appointments.")


def managed_appointment(
    appointment_id: int, user: CurrentUser, db: DatabaseSession,
) -> tuple[Doctor, Appointment]:
    appointment = appointments.get_appointment(db, appointment_id)
    doctor = appointments.get_booking_doctor(db, appointment.doctor_id, lock=True)
    require_booking_manager(doctor, user)
    # Another request may have changed the appointment while we waited for the lock.
    db.refresh(appointment)
    return doctor, appointment


ManagedAppointment = Annotated[tuple[Doctor, Appointment], Depends(managed_appointment)]


@router.get("/doctors/{doctor_id}/available-slots", response_model=list[AvailableSlot])
def read_available_slots(
    doctor_id: int, day: Annotated[date, Query()],
    db: DatabaseSession, settings: AppSettings,
) -> list[AvailableSlot]:
    doctor = appointments.get_booking_doctor(db, doctor_id)
    return appointments.available_slots(db, doctor, day, settings.timezone)


@router.post("/appointments", response_model=AppointmentRead, status_code=status.HTTP_201_CREATED)
def add_appointment(
    data: AppointmentCreate, user: CurrentUser, db: DatabaseSession,
    settings: AppSettings,
) -> AppointmentRead:
    doctor = appointments.get_booking_doctor(db, data.doctor_id, lock=True)
    require_booking_manager(doctor, user)
    appointment = appointments.create_appointment(db, doctor, data, settings.timezone)
    appointment.booked_by_user_id = user.id
    save_appointment(db)
    return AppointmentRead.model_validate(appointment)


@router.get("/appointments", response_model=AppointmentPage)
def browse_appointments(
    user: CurrentUser, db: DatabaseSession, settings: AppSettings, response: Response,
    doctor_id: Annotated[int | None, Query(gt=0)] = None,
    patient_id: Annotated[int | None, Query(gt=0)] = None,
    date_from: date | None = None, date_to: date | None = None,
    status: Literal["scheduled", "completed", "cancelled", "no_show"] | None = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> AppointmentPage:
    response.headers["Cache-Control"] = "no-store"
    return appointments.list_appointments(
        db, user, settings.timezone, doctor_id=doctor_id, patient_id=patient_id,
        date_from=date_from, date_to=date_to, status=status, offset=offset, limit=limit,
    )


@router.put("/appointments/{appointment_id}/no-show", response_model=AppointmentRead)
def mark_appointment_no_show(managed: ManagedAppointment, db: DatabaseSession) -> AppointmentRead:
    appointment = appointments.mark_no_show(db, managed[1])
    save_appointment(db)
    return AppointmentRead.model_validate(appointment)


@router.get("/appointments/{appointment_id}", response_model=AppointmentRead)
def read_appointment(
    managed: ManagedAppointment,
) -> AppointmentRead:
    return AppointmentRead.model_validate(managed[1])


@router.put("/appointments/{appointment_id}/reschedule", response_model=AppointmentRead)
def move_appointment(
    data: AppointmentReschedule, managed: ManagedAppointment,
    db: DatabaseSession, settings: AppSettings,
) -> AppointmentRead:
    doctor, appointment = managed
    appointments.reschedule_appointment(db, doctor, appointment, data.start_at, settings.timezone)
    save_appointment(db)
    return AppointmentRead.model_validate(appointment)


@router.put("/appointments/{appointment_id}/cancel", response_model=AppointmentRead)
def cancel_appointment(
    managed: ManagedAppointment, db: DatabaseSession,
) -> AppointmentRead:
    _, appointment = managed
    appointments.cancel_appointment(db, appointment)
    save_appointment(db)
    return AppointmentRead.model_validate(appointment)


@router.get("/doctors/{doctor_id}/booking-status", response_model=BookingStatus)
def read_booking_status(
    doctor_id: int, day: Annotated[date, Query()],
    db: DatabaseSession, settings: AppSettings,
) -> BookingStatus:
    doctor = appointments.get_booking_doctor(db, doctor_id)
    slots = appointments.available_slots(db, doctor, day, settings.timezone)
    return BookingStatus(remaining_slots=len(slots), is_fully_booked=not slots)


@router.post("/guest/appointments", response_model=GuestBookingConfirmation, status_code=201)
def book_as_guest(
    data: GuestBookingCreate, db: DatabaseSession, settings: AppSettings,
    response: Response, user: OptionalUser,
) -> GuestBookingConfirmation:
    doctor = appointments.get_booking_doctor(db, data.doctor_id, lock=True)
    appointments.select_slot(db, doctor, data.start_at, settings.timezone)
    # Never link an unverified guest to an existing patient by name or phone.
    patient = create_patient(db, PatientCreate(full_name=data.full_name, phone=data.phone), commit=False)
    appointment = appointments.create_appointment(db, doctor, AppointmentCreate(
        doctor_id=doctor.id, patient_id=patient.id, start_at=data.start_at,
    ), settings.timezone)
    token = create_session_token()
    appointment.booked_by_user_id = user.id if user is not None else None
    appointment.guest_token_hash = hash_session_token(token)
    save_appointment(db)
    response.headers["Cache-Control"] = "no-store"
    return GuestBookingConfirmation(
        **GuestBookingRead.model_validate(appointment).model_dump(), management_token=token,
    )


def guest_appointment(
    appointment_id: int, db: DatabaseSession, response: Response,
    token: Annotated[str, Header(alias="X-Booking-Token", min_length=32, max_length=128)],
) -> tuple[Doctor, Appointment]:
    # Use the same failure for unknown IDs and invalid tokens.
    appointment = db.get(Appointment, appointment_id)
    if appointment is None or not compare_digest(
        appointment.guest_token_hash or "", hash_session_token(token),
    ):
        raise AuthenticationRequiredError("Invalid booking credentials.")
    doctor = appointments.get_booking_doctor(db, appointment.doctor_id, lock=True)
    db.refresh(appointment)
    if appointment.end_at + timedelta(days=1) < datetime.now(timezone.utc):
        raise AuthenticationRequiredError("Booking access has expired.")
    response.headers["Cache-Control"] = "no-store"
    return doctor, appointment


GuestAppointment = Annotated[tuple[Doctor, Appointment], Depends(guest_appointment)]


@router.get("/guest/appointments/{appointment_id}", response_model=GuestBookingRead)
def read_guest_booking(managed: GuestAppointment) -> GuestBookingRead:
    return GuestBookingRead.model_validate(managed[1])


@router.put("/guest/appointments/{appointment_id}/cancel", response_model=GuestBookingRead)
def cancel_guest_booking(managed: GuestAppointment, db: DatabaseSession) -> GuestBookingRead:
    appointments.cancel_appointment(db, managed[1])
    save_appointment(db)
    return GuestBookingRead.model_validate(managed[1])


@router.put("/guest/appointments/{appointment_id}/reschedule", response_model=GuestBookingRead)
def move_guest_booking(
    data: AppointmentReschedule, managed: GuestAppointment,
    db: DatabaseSession, settings: AppSettings,
) -> GuestBookingRead:
    doctor, appointment = managed
    appointments.reschedule_appointment(db, doctor, appointment, data.start_at, settings.timezone)
    save_appointment(db)
    return GuestBookingRead.model_validate(appointment)


@router.get("/my/appointments", response_model=list[GuestBookingRead])
def my_bookings(user: AuthenticatedUser, db: DatabaseSession, response: Response) -> list[GuestBookingRead]:
    response.headers["Cache-Control"] = "no-store"
    bookings = db.scalars(select(Appointment).where(
        Appointment.booked_by_user_id == user.id,
    ).order_by(Appointment.start_at.desc()).limit(100))
    return [GuestBookingRead.model_validate(booking) for booking in bookings]


def owned_appointment(
    appointment_id: int, user: AuthenticatedUser, db: DatabaseSession,
    response: Response,
) -> tuple[Doctor, Appointment]:
    appointment = appointments.get_appointment(db, appointment_id)
    if appointment.booked_by_user_id != user.id:
        raise ForbiddenError("You can manage only your own bookings.")
    doctor = appointments.get_booking_doctor(db, appointment.doctor_id, lock=True)
    db.refresh(appointment)
    response.headers["Cache-Control"] = "no-store"
    return doctor, appointment


OwnedAppointment = Annotated[tuple[Doctor, Appointment], Depends(owned_appointment)]


@router.put("/my/appointments/{appointment_id}/cancel", response_model=GuestBookingRead)
def cancel_owned_booking(managed: OwnedAppointment, db: DatabaseSession) -> GuestBookingRead:
    appointments.cancel_appointment(db, managed[1])
    save_appointment(db)
    return GuestBookingRead.model_validate(managed[1])


@router.put("/my/appointments/{appointment_id}/reschedule", response_model=GuestBookingRead)
def move_owned_booking(
    data: AppointmentReschedule, managed: OwnedAppointment,
    db: DatabaseSession, settings: AppSettings,
) -> GuestBookingRead:
    doctor, appointment = managed
    appointments.reschedule_appointment(db, doctor, appointment, data.start_at, settings.timezone)
    save_appointment(db)
    return GuestBookingRead.model_validate(appointment)
