from fastapi import APIRouter

from app.schemas.clinic import ClinicContact
from app.services.clinic import load_clinic_contact

router = APIRouter(prefix="/clinic-contact-details", tags=["clinic"])


@router.get("", response_model=ClinicContact, summary="Get the clinic's public contact details")
def read_clinic_contact() -> ClinicContact:
    return load_clinic_contact()
