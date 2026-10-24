"""Patient text messages: booking confirmations and day-of reminders, via an outbox table."""

import asyncio
import logging
from collections.abc import Callable
from datetime import datetime, time, timedelta, timezone
from typing import Protocol
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import Appointment, Doctor, Patient, SmsMessage, Visit
from app.services.clinic import load_clinic_contact

logger = logging.getLogger(__name__)

# A reminder this close to the session is no use, e.g. after the worker was down.
REMINDER_CUTOFF = timedelta(minutes=30)


def normalize_phone(phone: str) -> str:
    """Sri Lankan numbers to +94 form, e.g. "077 123 4567" -> "+94771234567"; others keep their digits."""
    digits = "".join(char for char in phone if char.isdigit())
    if phone.strip().startswith("+"):
        return f"+{digits}"
    if len(digits) == 10 and digits.startswith("0"):
        return f"+94{digits[1:]}"
    return digits


def _format_code(code: str) -> str:
    return f"{code[:5]}-{code[5:]}" if len(code) == 10 else code


def _day(moment: datetime) -> str:
    return f"{moment:%a} {moment.day} {moment:%b}"  # "Mon 12 Oct"


def _clock(moment: datetime) -> str:
    return f"{moment.hour % 12 or 12}:{moment:%M %p}"  # "5:00 PM"


def _clinic_name() -> str:
    try:
        return load_clinic_contact().name
    except Exception:  # The message still makes sense without it.
        return "The clinic"


def confirmation_text(appointment: Appointment, doctor: Doctor, clinic_timezone: str) -> str:
    start = appointment.start_at.astimezone(ZoneInfo(clinic_timezone))
    return (f"{_clinic_name()}: Booked with {doctor.display_name}, {_day(start)}, "
            f"session starts {_clock(start)}. Your number: {appointment.appointment_number}. "
            f"Booking ID {appointment.id}.")


def reminder_text(appointment: Appointment, doctor: Doctor, clinic_timezone: str) -> str:
    start = appointment.start_at.astimezone(ZoneInfo(clinic_timezone))
    return (f"{_clinic_name()}: Reminder - today with {doctor.display_name}, session starts "
            f"{_clock(start)}. Your number: {appointment.appointment_number}. "
            f"Check-in code {_format_code(appointment.checkin_code)}. Please arrive a little early.")


def queue_confirmation(db: Session, appointment: Appointment, clinic_timezone: str) -> SmsMessage:
    """Call before committing the booking, so the message and the booking are saved together."""
    db.flush()  # A new booking needs its ID for the message.
    patient = db.get(Patient, appointment.patient_id)
    message = SmsMessage(
        appointment_id=appointment.id, session_start=appointment.start_at, kind="confirmation",
        phone=normalize_phone(patient.phone),
        body=confirmation_text(appointment, db.get(Doctor, appointment.doctor_id), clinic_timezone),
        status="queued", created_at=datetime.now(timezone.utc),
    )
    db.add(message)
    return message


def reminder_due_at(session_start: datetime, settings: Settings) -> datetime:
    local = session_start.astimezone(ZoneInfo(settings.timezone))
    morning = datetime.combine(local.date(), time(settings.sms_reminder_hour), local.tzinfo)
    return max(morning, local - timedelta(hours=settings.sms_reminder_hours_before))


def queue_due_reminders(db: Session, settings: Settings) -> int:
    """Queue a reminder for each of today's bookings whose reminder time has come."""
    now = datetime.now(timezone.utc)
    rows = db.execute(
        select(Appointment, Patient.phone, Doctor)
        .join(Patient, Patient.id == Appointment.patient_id)
        .join(Doctor, Doctor.id == Appointment.doctor_id)
        .outerjoin(Visit, Visit.appointment_id == Appointment.id)
        .where(Appointment.status == "scheduled", Visit.id.is_(None),
               Appointment.start_at > now + REMINDER_CUTOFF, Appointment.start_at < now + timedelta(hours=24))
    ).all()
    queued = 0
    for appointment, phone, doctor in rows:
        due_at = reminder_due_at(appointment.start_at, settings)
        if now < due_at:
            continue
        # Booked or moved after the reminder time: the confirmation has just told them.
        if db.scalar(select(SmsMessage.id).where(
            SmsMessage.appointment_id == appointment.id, SmsMessage.kind == "confirmation",
            SmsMessage.session_start == appointment.start_at, SmsMessage.created_at >= due_at,
        )):
            continue
        result = db.execute(insert(SmsMessage).values(
            appointment_id=appointment.id, session_start=appointment.start_at, kind="reminder",
            phone=normalize_phone(phone), body=reminder_text(appointment, doctor, settings.timezone),
            status="queued", created_at=now,
        ).on_conflict_do_nothing(
            index_elements=["appointment_id", "session_start"], index_where=SmsMessage.kind == "reminder",
        ).returning(SmsMessage.id))
        queued += result.first() is not None
    db.commit()
    return queued


class SmsSender(Protocol):
    """Sends one message; returns "sent" or "logged", or raises on failure."""

    def send(self, phone: str, body: str) -> str: ...


class OutboxOnlySender:
    """No provider: keep the message in the outbox for staff to see."""

    def send(self, phone: str, body: str) -> str:
        return "logged"


def sender_for(settings: Settings) -> SmsSender:
    return OutboxOnlySender()


def deliver_queued(db: Session, sender: SmsSender, limit: int = 50) -> int:
    """Hand queued messages to the provider; rows are locked so two workers never send one twice."""
    messages = list(db.scalars(
        select(SmsMessage).where(SmsMessage.status == "queued")
        .order_by(SmsMessage.created_at).limit(limit).with_for_update(skip_locked=True)
    ))
    for message in messages:
        try:
            message.status = sender.send(message.phone, message.body)
            message.sent_at = datetime.now(timezone.utc)
        except Exception as error:  # Keep going; the failure is recorded on the message.
            message.status = "failed"
            message.error = str(error)[:255]
    db.commit()
    return len(messages)


def run_once(session_factory: Callable[[], Session], settings: Settings) -> None:
    with session_factory() as db:
        queue_due_reminders(db, settings)
        deliver_queued(db, sender_for(settings))


async def run_worker(session_factory: Callable[[], Session], settings: Settings) -> None:
    """Background loop inside the API process."""
    while True:
        try:
            await asyncio.to_thread(run_once, session_factory, settings)
        except Exception:
            logger.exception("SMS worker run failed")
        await asyncio.sleep(settings.sms_worker_interval_seconds)


def outbox_page(db: Session, offset: int, limit: int) -> tuple[list[SmsMessage], int]:
    rows = list(db.scalars(select(SmsMessage).order_by(SmsMessage.created_at.desc(), SmsMessage.id.desc())
                           .offset(offset).limit(limit)))
    return rows, db.scalar(select(func.count()).select_from(SmsMessage)) or 0
