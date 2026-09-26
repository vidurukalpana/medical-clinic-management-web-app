"""Public clinic details shared by the website and the chat assistant."""

from pathlib import Path

from app.schemas.clinic import ClinicContact

CONTENT_DIRECTORY = Path(__file__).resolve().parent.parent / "content"
CLINIC_CONTACT_PATH = CONTENT_DIRECTORY / "clinic_contact.json"


def load_clinic_contact() -> ClinicContact:
    # Read on every call so edits apply without restarting the application.
    return ClinicContact.model_validate_json(CLINIC_CONTACT_PATH.read_text(encoding="utf-8"))
