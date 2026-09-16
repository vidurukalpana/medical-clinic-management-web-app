from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.core.config import Settings, get_settings
from app.dependencies import CurrentUser, DatabaseSession
from app.errors import ForbiddenError
from app.errors.appointments import save_appointment
from app.models import Appointment, Doctor, User, UserRole
from app.schemas.appointment import (
    AppointmentCreate, AppointmentRead, AppointmentReschedule, AvailableSlot, BookingStatus,
)
from app.services import appointments

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
    doctor_id: int, day: Annotated[date, Query()], _: CurrentUser,
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
    save_appointment(db)
    return AppointmentRead.model_validate(appointment)


@router.get("/appointments/{appointment_id}", response_model=AppointmentRead)
def read_appointment(
    appointment_id: int, _: CurrentUser, db: DatabaseSession,
) -> AppointmentRead:
    return AppointmentRead.model_validate(appointments.get_appointment(db, appointment_id))


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
    doctor_id: int, day: Annotated[date, Query()], _: CurrentUser,
    db: DatabaseSession, settings: AppSettings,
) -> BookingStatus:
    doctor = appointments.get_booking_doctor(db, doctor_id)
    slots = appointments.available_slots(db, doctor, day, settings.timezone)
    return BookingStatus(remaining_slots=len(slots), is_fully_booked=not slots)
