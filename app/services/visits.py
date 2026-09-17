from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.errors import BadRequestError, ConflictError, DoctorFullyBookedError, ForbiddenError, NotFoundError
from app.models import Appointment, Doctor, Patient, User, UserRole, Visit
from app.schemas.visit import (
    DashboardAction, DashboardAppointment, DashboardRead, DashboardSummary,
    DashboardVisit, DoctorQueue, VisitUpdate,
)
from app.services.patients import get_patient
from app.services.appointments import available_slots


def clinic_today(clinic_timezone: str) -> date:
    return datetime.now(ZoneInfo(clinic_timezone)).date()


def get_visit(db: Session, visit_id: int) -> Visit:
    visit = db.get(Visit, visit_id)
    if visit is None:
        raise NotFoundError("Visit")
    return visit


def list_queue(db: Session, doctor_id: int, day: date) -> list[Visit]:
    return list(db.scalars(
        select(Visit)
        .outerjoin(Visit.appointment)
        .options(joinedload(Visit.appointment))
        .where(Visit.doctor_id == doctor_id, Visit.visit_date == day)
        .order_by(Appointment.start_at.asc().nulls_last(), Visit.queue_number)
    ))


def create_visit(
    db: Session,
    doctor: Doctor,
    patient_id: int,
    day: date,
    appointment: Appointment | None = None,
) -> Visit:
    """Allocate a number while the caller holds the doctor's row lock."""
    if not doctor.is_active or not doctor.user.is_active:
        raise ConflictError("The doctor is inactive.")
    get_patient(db, patient_id)
    if appointment is not None:
        if appointment.status != "scheduled":
            raise ConflictError("Only scheduled appointments can be checked in.")
        if db.scalar(select(Visit.id).where(Visit.appointment_id == appointment.id)):
            raise ConflictError("This appointment has already been checked in.")
    if db.scalar(select(Visit.id).where(
        Visit.doctor_id == doctor.id,
        Visit.patient_id == patient_id,
        Visit.visit_date == day,
        Visit.status.in_(("waiting", "in_progress")),
    )):
        raise ConflictError("This patient is already in this doctor's queue today.")
    last_number = db.scalar(select(func.max(Visit.queue_number)).where(
        Visit.doctor_id == doctor.id, Visit.visit_date == day,
    )) or 0
    visit = Visit(
        appointment_id=appointment.id if appointment else None,
        doctor_id=doctor.id,
        patient_id=patient_id,
        visit_date=day,
        queue_number=last_number + 1,
        status="waiting",
    )
    db.add(visit)
    return visit


def create_walk_in(
    db: Session, doctor: Doctor, patient_id: int,
    clinic_timezone: str,
) -> Visit:
    """Reserve today's next free slot and queue the patient atomically."""
    day = clinic_today(clinic_timezone)
    visit = create_visit(db, doctor, patient_id, day)
    slots = available_slots(db, doctor, day, clinic_timezone)
    if not slots:
        raise DoctorFullyBookedError()
    slot = slots[0]
    visit.appointment = Appointment(
        doctor_id=doctor.id,
        patient_id=patient_id,
        start_at=slot.start_at,
        end_at=slot.end_at,
        status="scheduled",
    )
    return visit


def check_in(
    db: Session, doctor: Doctor, appointment: Appointment,
    clinic_timezone: str,
) -> Visit:
    day = clinic_today(clinic_timezone)
    if appointment.start_at.astimezone(ZoneInfo(clinic_timezone)).date() != day:
        raise BadRequestError("Check-in is allowed only on the appointment's clinic date.")
    return create_visit(
        db, doctor, appointment.patient_id, day, appointment,
    )


def update_visit(db: Session, visit: Visit, data: VisitUpdate) -> Visit:
    if visit.status in ("completed", "cancelled"):
        raise ConflictError("Completed or cancelled visits cannot be edited.")
    transitions = {
        "waiting": {"waiting", "in_progress", "cancelled"},
        "in_progress": {"in_progress", "completed", "cancelled"},
    }
    if data.status is not None and data.status not in transitions[visit.status]:
        raise ConflictError("Invalid consultation status transition.")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(visit, field, value)
    if visit.appointment_id is not None and data.status in ("completed", "cancelled"):
        appointment = db.get(Appointment, visit.appointment_id)
        appointment.status = data.status
    return visit


def dashboard(
    db: Session, user: User, clinic_timezone: str, doctor_id: int | None = None,
) -> DashboardRead:
    """A clinic-local daily snapshot, scoped before any patient rows are queried."""
    now = datetime.now(ZoneInfo(clinic_timezone))
    day = now.date()
    start = datetime.combine(day, time.min, now.tzinfo)
    end = datetime.combine(day + timedelta(days=1), time.min, now.tzinfo)
    if user.role not in (UserRole.ADMINISTRATOR, UserRole.DOCTOR):
        raise ForbiddenError("Staff permission required.")
    doctors_query = select(Doctor).options(joinedload(Doctor.user)).order_by(Doctor.display_name, Doctor.id)
    if user.role == UserRole.DOCTOR:
        if user.doctor is None or (doctor_id is not None and doctor_id != user.doctor.id):
            raise ForbiddenError("You can view only your own dashboard.")
        doctors_query = doctors_query.where(Doctor.user_id == user.id)
    if doctor_id is not None:
        doctors_query = doctors_query.where(Doctor.id == doctor_id)
    doctors = list(db.scalars(doctors_query))
    if doctor_id is not None and not doctors:
        raise NotFoundError("Doctor")
    doctor_ids = [doctor.id for doctor in doctors]
    doctor_names = {doctor.id: doctor.display_name for doctor in doctors}
    appointment_rows = db.execute(
        select(Appointment, Patient.full_name, Visit.id)
        .join(Patient, Patient.id == Appointment.patient_id)
        .outerjoin(Visit, Visit.appointment_id == Appointment.id)
        .where(Appointment.doctor_id.in_(doctor_ids),
               Appointment.start_at >= start, Appointment.start_at < end)
        .order_by(Appointment.start_at, Appointment.id)
    ).all()
    appointment_items = []
    for appointment, patient_name, visit_id in appointment_rows:
        actions = []
        if appointment.status == "scheduled" and visit_id is None:
            actions.append(DashboardAction(label="Check in", method="POST",
                                           path=f"/api/appointments/{appointment.id}/check-in"))
            if appointment.end_at <= now:
                actions.append(DashboardAction(label="Mark no-show", method="PUT",
                                               path=f"/api/appointments/{appointment.id}/no-show"))
            actions.append(DashboardAction(label="Cancel", method="PUT",
                                           path=f"/api/appointments/{appointment.id}/cancel"))
        appointment_items.append(DashboardAppointment(
            **{key: getattr(appointment, key) for key in
               ("id", "doctor_id", "patient_id", "start_at", "end_at", "status")},
            patient_name=patient_name, doctor_name=doctor_names[appointment.doctor_id],
            visit_id=visit_id, actions=actions,
        ))
    visit_rows = db.execute(
        select(Visit, Patient.full_name)
        .join(Patient, Patient.id == Visit.patient_id)
        .outerjoin(Visit.appointment)
        .options(joinedload(Visit.appointment))
        .where(Visit.doctor_id.in_(doctor_ids), Visit.visit_date == day)
        .order_by(Appointment.start_at.asc().nulls_last(), Visit.queue_number, Visit.id)
    ).all()
    queues: dict[int, list[DashboardVisit]] = {doctor.id: [] for doctor in doctors}
    for visit, patient_name in visit_rows:
        if visit.status not in ("waiting", "in_progress"):
            continue
        next_status = "in_progress" if visit.status == "waiting" else "completed"
        queues[visit.doctor_id].append(DashboardVisit(
            **{key: getattr(visit, key) for key in
               ("id", "appointment_id", "doctor_id", "patient_id", "visit_date",
                "queue_number", "start_at", "end_at", "status")},
            patient_name=patient_name,
            actions=[
                DashboardAction(label="Start" if visit.status == "waiting" else "Complete",
                                method="PATCH", path=f"/api/visits/{visit.id}", body={"status": next_status}),
                DashboardAction(label="Cancel", method="PATCH", path=f"/api/visits/{visit.id}",
                                body={"status": "cancelled"}),
            ],
        ))
    return DashboardRead(
        day=day, timezone=clinic_timezone, generated_at=now,
        summary=DashboardSummary(
            appointments=len(appointment_items),
            scheduled=sum(a.status == "scheduled" for a in appointment_items),
            waiting=sum(v.status == "waiting" for v, _ in visit_rows),
            in_progress=sum(v.status == "in_progress" for v, _ in visit_rows),
            completed=sum(v.status == "completed" for v, _ in visit_rows),
            cancelled=sum(a.status == "cancelled" for a in appointment_items),
            no_show=sum(a.status == "no_show" for a in appointment_items),
        ),
        appointments=appointment_items,
        doctor_queues=[DoctorQueue(
            doctor_id=doctor.id, doctor_name=doctor.display_name,
            is_active=doctor.is_active and doctor.user.is_active,
            waiting_count=sum(v.status == "waiting" for v in queues[doctor.id]),
            in_progress_count=sum(v.status == "in_progress" for v in queues[doctor.id]),
            patients=queues[doctor.id],
        ) for doctor in doctors],
    )
