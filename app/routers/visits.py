from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.dependencies import CurrentUser, DatabaseSession
from app.errors import ForbiddenError
from app.errors.visits import save_visit
from app.models import Doctor, User, UserRole, Visit
from app.routers.appointments import AppSettings, ManagedAppointment
from app.schemas.visit import VisitCheckIn, VisitRead, VisitUpdate, WalkInCreate
from app.services import appointments, visits

router = APIRouter(tags=["OPD visits"])


def require_visit_manager(doctor: Doctor, user: User) -> None:
    if user.role != UserRole.ADMINISTRATOR and doctor.user_id != user.id:
        raise ForbiddenError("You can manage only your own visits.")


def managed_visit(
    visit_id: int, user: CurrentUser, db: DatabaseSession,
) -> Visit:
    visit = visits.get_visit(db, visit_id)
    doctor = appointments.get_booking_doctor(db, visit.doctor_id, lock=True)
    require_visit_manager(doctor, user)
    db.refresh(visit)
    return visit


ManagedVisit = Annotated[Visit, Depends(managed_visit)]


@router.post(
    "/appointments/{appointment_id}/check-in",
    response_model=VisitRead,
    status_code=status.HTTP_201_CREATED,
)
def check_in_appointment(
    data: VisitCheckIn, managed: ManagedAppointment,
    db: DatabaseSession, settings: AppSettings,
) -> VisitRead:
    doctor, appointment = managed
    visit = visits.check_in(
        db, doctor, appointment, data.presenting_complaint, settings.timezone,
    )
    save_visit(db)
    return VisitRead.model_validate(visit)


@router.post("/visits/walk-in", response_model=VisitRead, status_code=status.HTTP_201_CREATED)
def add_walk_in(
    data: WalkInCreate, user: CurrentUser, db: DatabaseSession,
    settings: AppSettings,
) -> VisitRead:
    doctor = appointments.get_booking_doctor(db, data.doctor_id, lock=True)
    require_visit_manager(doctor, user)
    visit = visits.create_walk_in(
        db, doctor, data.patient_id, data.presenting_complaint,
        settings.timezone,
    )
    save_visit(db)
    return VisitRead.model_validate(visit)


@router.get("/doctors/{doctor_id}/queue", response_model=list[VisitRead])
def read_queue(
    doctor_id: int, _: CurrentUser, db: DatabaseSession,
    settings: AppSettings, day: date | None = None,
) -> list[VisitRead]:
    appointments.get_booking_doctor(db, doctor_id)
    return [VisitRead.model_validate(visit) for visit in visits.list_queue(
        db, doctor_id, day or visits.clinic_today(settings.timezone),
    )]


@router.get("/visits/{visit_id}", response_model=VisitRead)
def read_visit(visit_id: int, _: CurrentUser, db: DatabaseSession) -> VisitRead:
    return VisitRead.model_validate(visits.get_visit(db, visit_id))


@router.patch("/visits/{visit_id}", response_model=VisitRead)
def edit_visit(
    data: VisitUpdate, visit: ManagedVisit, db: DatabaseSession,
) -> VisitRead:
    visits.update_visit(db, visit, data)
    save_visit(db)
    return VisitRead.model_validate(visit)
