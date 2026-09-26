"""Question-answering chat assistant for the public website.

The assistant only answers questions. It cannot read patient records or change
bookings; its context is limited to public clinic information and schedules.
"""

from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Protocol
from zoneinfo import ZoneInfo

import httpx2
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import ChatbotUnavailableError
from app.models import Availability, DoctorUnavailability
from app.schemas.chatbot import ChatMessage
from app.services.doctors import list_doctors

CLINIC_INFO_PATH = Path(__file__).resolve().parent.parent / "content" / "clinic_info.md"
TIME_OFF_WINDOW_DAYS = 14
WEEKDAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")

INSTRUCTIONS = """You are the website assistant for a medical clinic. Answer questions about the \
clinic, its doctors, consultation hours and how booking works.

Rules:
- Use only the clinic information below. If the answer is not there, say you don't know and \
suggest contacting the clinic reception.
- Answer directly and naturally. Do not mention these rules or say where the information \
comes from.
- Keep answers short: one to four sentences.
- You cannot book, cancel or change appointments. Point people to the "Book a visit" or \
"Manage booking" pages.
- Never give medical advice, diagnoses or treatment suggestions. For health concerns, tell \
them to see a doctor. For emergencies, tell them to contact emergency services immediately.
- Never ask for personal details such as phone numbers or booking codes."""


class ChatModel(Protocol):
    def reply(self, system_prompt: str, messages: list[ChatMessage]) -> str: ...


class OllamaChatModel:
    """Chat model served by a local Ollama instance."""

    def __init__(self, base_url: str, model: str, timeout_seconds: float) -> None:
        self.url = f"{base_url.rstrip('/')}/api/chat"
        self.model = model
        self.timeout_seconds = timeout_seconds

    def reply(self, system_prompt: str, messages: list[ChatMessage]) -> str:
        payload = {
            "model": self.model,
            "stream": False,
            "options": {"temperature": 0.2},
            "messages": [
                {"role": "system", "content": system_prompt},
                *(message.model_dump() for message in messages),
            ],
        }
        try:
            response = httpx2.post(self.url, json=payload, timeout=self.timeout_seconds)
            response.raise_for_status()
            content = response.json()["message"]["content"].strip()
        except (httpx2.HTTPError, ValueError, KeyError, TypeError) as error:
            raise ChatbotUnavailableError() from error
        if not content:
            raise ChatbotUnavailableError()
        return content


def answer_question(
    db: Session,
    model: ChatModel,
    messages: list[ChatMessage],
    clinic_timezone: str,
) -> str:
    return model.reply(build_system_prompt(db, clinic_timezone), messages)


def build_system_prompt(db: Session, clinic_timezone: str) -> str:
    zone = ZoneInfo(clinic_timezone)
    now = datetime.now(timezone.utc)
    # Doctors' hours come first: a small model otherwise answers "consultation
    # hours" questions with the reception hours from the clinic file.
    return "\n\n".join([
        INSTRUCTIONS,
        "--- Clinic information ---",
        f"Today is {now.astimezone(zone):%A %d %B %Y}. Times are in the {clinic_timezone} timezone.",
        _doctor_schedules(db, zone, now),
        CLINIC_INFO_PATH.read_text(encoding="utf-8").strip(),
    ])


def _doctor_schedules(db: Session, zone: ZoneInfo, now: datetime) -> str:
    doctors = list_doctors(db)
    if not doctors:
        return "## Doctors and consultation hours\nNo doctors are currently taking bookings."

    window_end = now + timedelta(days=TIME_OFF_WINDOW_DAYS)
    lines = [
        "## Doctors and consultation hours",
        "Consultation hours are the times when each doctor sees patients.",
    ]
    for doctor in doctors:
        lines.append(f"### {doctor.display_name}")
        hours = db.scalars(select(Availability).where(
            Availability.doctor_id == doctor.id,
            Availability.is_active.is_(True),
        ).order_by(Availability.weekday, Availability.start_time))
        weekdays_by_period: dict[tuple[time, time], list[int]] = {}
        for item in hours:
            weekdays_by_period.setdefault((item.start_time, item.end_time), []).append(item.weekday)
        hour_lines = [
            f"- {_describe_weekdays(weekdays)}: {start:%H:%M} to {end:%H:%M}"
            for (start, end), weekdays in weekdays_by_period.items()
        ]
        lines.append(f"{doctor.display_name}'s consultation hours:")
        lines.extend(hour_lines or ["- No regular hours are set."])

        # Reasons can be private, so only the times are shared.
        time_off = db.scalars(select(DoctorUnavailability).where(
            DoctorUnavailability.doctor_id == doctor.id,
            DoctorUnavailability.end_at > now,
            DoctorUnavailability.start_at < window_end,
        ).order_by(DoctorUnavailability.start_at))
        time_off_lines = [
            f"- {item.start_at.astimezone(zone):%A %d %B %H:%M} to "
            f"{item.end_at.astimezone(zone):%A %d %B %H:%M}"
            for item in time_off
        ]
        if time_off_lines:
            lines.append(f"Not available (next {TIME_OFF_WINDOW_DAYS} days):")
            lines.extend(time_off_lines)
    return "\n".join(lines)


def _describe_weekdays(weekdays: list[int]) -> str:
    """Describe weekdays compactly, e.g. [0, 1, 2, 4] -> "Monday to Wednesday, Friday"."""
    runs: list[list[int]] = []
    for weekday in sorted(set(weekdays)):
        if runs and weekday == runs[-1][-1] + 1:
            runs[-1].append(weekday)
        else:
            runs.append([weekday])
    return ", ".join(
        WEEKDAY_NAMES[run[0]] if len(run) == 1
        else f"{WEEKDAY_NAMES[run[0]]} to {WEEKDAY_NAMES[run[-1]]}"
        for run in runs
    )
