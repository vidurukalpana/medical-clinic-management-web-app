from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.errors import BadRequestError, ConflictError, DoctorFullyBookedError, ForbiddenError, NotFoundError
from app.models import (
    Appointment, Availability, Doctor, DoctorUnavailability, Patient, SessionArrival, User, UserRole, Visit,
)
from app.schemas.visit import (
    DashboardAction, DashboardAppointment, DashboardRead, DashboardSummary,
    DashboardVisit, DoctorQueue, LiveQueueRead, LiveSession, QueueSession, SeenVisit,
    SessionArrivalRead, VisitUpdate,
)
from app.services.doctors import list_doctors
from app.services.patients import get_patient
from app.services.appointments import booking_sessions, next_appointment_number


# How long past its scheduled end a session with patients still waiting counts as running late.
RUNNING_LATE_LIMIT = timedelta(hours=2)


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
        .order_by(Appointment.start_at.asc().nulls_last(),
                  Appointment.appointment_number, Visit.queue_number)
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
        checked_in_at=datetime.now(timezone.utc),
    )
    db.add(visit)
    return visit


def create_walk_in(
    db: Session, doctor: Doctor, patient_id: int,
    clinic_timezone: str,
) -> Visit:
    """Give the patient the next number in today's earliest open session and queue them atomically."""
    day = clinic_today(clinic_timezone)
    visit = create_visit(db, doctor, patient_id, day)
    session = next((session for session in booking_sessions(db, doctor, day, clinic_timezone)
                    if session.remaining), None)
    if session is None:
        raise DoctorFullyBookedError()
    visit.appointment = Appointment(
        doctor_id=doctor.id,
        patient_id=patient_id,
        start_at=session.start_at,
        end_at=session.end_at,
        appointment_number=next_appointment_number(db, doctor.id, session.start_at),
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
    now = datetime.now(timezone.utc)
    if visit.status == "waiting" and data.status == "in_progress":
        visit.consult_started_at = now
        if visit.appointment is not None:
            # Seeing a patient shows the doctor is in, even if no one pressed "Doctor arrived".
            record_arrival(db, visit.doctor_id, visit.appointment.start_at, now)
    if visit.status == "in_progress" and data.status in ("completed", "cancelled"):
        visit.consult_ended_at = now
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
        .order_by(Appointment.start_at, Appointment.appointment_number, Appointment.id)
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
               ("id", "doctor_id", "patient_id", "start_at", "end_at", "appointment_number", "status",
                "cancelled_by_clinic")},
            patient_name=patient_name, doctor_name=doctor_names[appointment.doctor_id],
            visit_id=visit_id, actions=actions,
        ))
    visit_rows = db.execute(
        select(Visit, Patient.full_name)
        .join(Patient, Patient.id == Visit.patient_id)
        .outerjoin(Visit.appointment)
        .options(joinedload(Visit.appointment))
        .where(Visit.doctor_id.in_(doctor_ids), Visit.visit_date == day)
        .order_by(Appointment.start_at.asc().nulls_last(), Appointment.appointment_number,
                  Visit.queue_number, Visit.id)
    ).all()
    queues: dict[int, list[DashboardVisit]] = {doctor.id: [] for doctor in doctors}
    seen: dict[int, list[SeenVisit]] = {doctor.id: [] for doctor in doctors}
    for visit, patient_name in visit_rows:
        if visit.status == "completed":
            seen[visit.doctor_id].append(SeenVisit(
                id=visit.id, appointment_number=visit.appointment_number, patient_name=patient_name,
                consult_started_at=visit.consult_started_at, consult_ended_at=visit.consult_ended_at,
            ))
        if visit.status not in ("waiting", "in_progress"):
            continue
        next_status = "in_progress" if visit.status == "waiting" else "completed"
        queues[visit.doctor_id].append(DashboardVisit(
            **{key: getattr(visit, key) for key in
               ("id", "appointment_id", "doctor_id", "patient_id", "visit_date",
                "queue_number", "appointment_number", "start_at", "end_at", "status",
                "checked_in_at", "consult_started_at", "consult_ended_at")},
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
            session=queue_session(db, doctor.id, clinic_timezone),
            patients=queues[doctor.id],
            seen=sorted(seen[doctor.id], key=lambda item: item.consult_ended_at or now, reverse=True),
        ) for doctor in doctors],
    )


def live_queue(db: Session, clinic_timezone: str) -> LiveQueueRead:
    """Today's sessions with the number in the doctor's room and the numbers still to be seen."""
    now = datetime.now(ZoneInfo(clinic_timezone))
    day = now.date()
    day_start = datetime.combine(day, time.min, now.tzinfo)
    day_end = datetime.combine(day + timedelta(days=1), time.min, now.tzinfo)
    doctors = {doctor.id: doctor for doctor in list_doctors(db)}
    schedules = db.scalars(select(Availability).where(
        Availability.doctor_id.in_(doctors),
        Availability.weekday == day.weekday(),
        Availability.is_active.is_(True),
    ).order_by(Availability.start_time, Availability.doctor_id))
    blocked = db.execute(select(
        DoctorUnavailability.doctor_id, DoctorUnavailability.start_at, DoctorUnavailability.end_at,
    ).where(
        DoctorUnavailability.doctor_id.in_(doctors),
        DoctorUnavailability.start_at < day_end,
        DoctorUnavailability.end_at > day_start,
    )).all()
    bookings = db.execute(
        select(Appointment.doctor_id, Appointment.start_at, Appointment.appointment_number,
               Appointment.status, Visit.status.label("visit_status"))
        .outerjoin(Visit, Visit.appointment_id == Appointment.id)
        .where(Appointment.doctor_id.in_(doctors), Appointment.status != "cancelled",
               Appointment.start_at >= day_start, Appointment.start_at < day_end)
    ).all()
    attendance = attendance_on(db, list(doctors), day_start, day_end)
    sessions = []
    for schedule in schedules:
        start = datetime.combine(day, schedule.start_time, now.tzinfo)
        end = datetime.combine(day, schedule.end_time, now.tzinfo)
        rows = [row for row in bookings if row.doctor_id == schedule.doctor_id and row.start_at == start]
        in_room = [row.appointment_number for row in rows if row.visit_status == "in_progress"]
        if any(doctor_id == schedule.doctor_id and block_start < end and block_end > start
               for doctor_id, block_start, block_end in blocked):
            status = "unavailable"
        elif in_room:
            status = "in_progress"
        elif attendance.get((schedule.doctor_id, start), (None, None))[1] is not None:
            status = "ended"  # The doctor has left.
        elif (schedule.doctor_id, start) in attendance and (end > now or (
            now < end + RUNNING_LATE_LIMIT and any(row.visit_status == "waiting" for row in rows)
        )):
            status = "in_progress"  # Doctor in, between patients, or running late with patients waiting.
        elif end <= now:
            status = "ended"
        elif any(row.visit_status == "completed" for row in rows):
            status = "in_progress"
        else:
            status = "not_started"
        arrived_at, left_at = attendance.get((schedule.doctor_id, start), (None, None))
        sessions.append(LiveSession(
            doctor_id=schedule.doctor_id, doctor_name=doctors[schedule.doctor_id].display_name,
            start_at=start, end_at=end, status=status,
            doctor_arrived_at=arrived_at, doctor_left_at=left_at,
            now_serving=max(in_room) if in_room else None,
            # Booked numbers not yet seen, whether or not they have arrived.
            numbers_to_see=sorted(
                row.appointment_number for row in rows
                if row.status == "scheduled" and row.visit_status in (None, "waiting")
            ),
        ))
    return LiveQueueRead(day=day, generated_at=now, sessions=sessions)


def todays_sessions(
    db: Session, doctor_id: int, clinic_timezone: str, *, include_ended: bool = False,
) -> list[tuple[datetime, datetime]]:
    """Today's sessions not closed by time off; only those not yet ended unless `include_ended`."""
    now = datetime.now(ZoneInfo(clinic_timezone))
    day = now.date()
    blocked = db.execute(select(DoctorUnavailability.start_at, DoctorUnavailability.end_at).where(
        DoctorUnavailability.doctor_id == doctor_id,
        DoctorUnavailability.start_at < datetime.combine(day + timedelta(days=1), time.min, now.tzinfo),
        DoctorUnavailability.end_at > datetime.combine(day, time.min, now.tzinfo),
    )).all()
    sessions = []
    for schedule in db.scalars(select(Availability).where(
        Availability.doctor_id == doctor_id, Availability.weekday == day.weekday(),
        Availability.is_active.is_(True),
    ).order_by(Availability.start_time)):
        start = datetime.combine(day, schedule.start_time, now.tzinfo)
        end = datetime.combine(day, schedule.end_time, now.tzinfo)
        if (include_ended or end > now) and not any(
            start < block_end and end > block_start for block_start, block_end in blocked
        ):
            sessions.append((start, end))
    return sessions


def attendance_on(
    db: Session, doctor_ids: list[int], day_start: datetime, day_end: datetime,
) -> dict[tuple[int, datetime], tuple[datetime, datetime | None]]:
    """(doctor, session start) -> (arrived at, left at)."""
    return {
        (row.doctor_id, row.session_start): (row.arrived_at, row.left_at)
        for row in db.scalars(select(SessionArrival).where(
            SessionArrival.doctor_id.in_(doctor_ids),
            SessionArrival.session_start >= day_start, SessionArrival.session_start < day_end,
        ))
    }


def queue_session(db: Session, doctor_id: int, clinic_timezone: str) -> QueueSession | None:
    """The session to show on the dashboard: one the doctor is still in, even past its end, else the next."""
    now = datetime.now(timezone.utc)
    sessions = todays_sessions(db, doctor_id, clinic_timezone, include_ended=True)
    if not sessions:
        return None
    attendance = attendance_on(db, [doctor_id], sessions[0][0], sessions[-1][1])

    def view(start: datetime, end: datetime) -> QueueSession:
        arrived_at, left_at = attendance.get((doctor_id, start), (None, None))
        return QueueSession(start_at=start, end_at=end, doctor_arrived_at=arrived_at, doctor_left_at=left_at)

    # A session the doctor is still in, even past its end, so staff can record when they leave.
    still_in = [(start, end) for start, end in sessions
                if (doctor_id, start) in attendance and attendance[(doctor_id, start)][1] is None]
    if still_in:
        return view(*still_in[-1])
    upcoming = [(start, end) for start, end in sessions
                if end > now and attendance.get((doctor_id, start), (None, None))[1] is None]
    # Otherwise the current or next session, or the last one once all are over.
    return view(*(upcoming[0] if upcoming else sessions[-1]))


def record_arrival(db: Session, doctor_id: int, session_start: datetime, now: datetime) -> SessionArrival:
    """Keep the first arrival; the caller holds the doctor's row lock."""
    arrival = db.scalar(select(SessionArrival).where(
        SessionArrival.doctor_id == doctor_id, SessionArrival.session_start == session_start,
    ))
    if arrival is None:
        arrival = SessionArrival(doctor_id=doctor_id, session_start=session_start, arrived_at=now)
        db.add(arrival)
    return arrival


def _attendance_read(arrival: SessionArrival) -> SessionArrivalRead:
    return SessionArrivalRead(start_at=arrival.session_start, doctor_arrived_at=arrival.arrived_at,
                              doctor_left_at=arrival.left_at)


def mark_doctor_arrived(
    db: Session, doctor: Doctor, start_at: datetime, clinic_timezone: str,
) -> SessionArrivalRead:
    if not any(start == start_at for start, _ in todays_sessions(db, doctor.id, clinic_timezone)):
        raise NotFoundError("Session today")
    arrival = record_arrival(db, doctor.id, start_at, datetime.now(timezone.utc))
    db.commit()
    return _attendance_read(arrival)


def mark_doctor_left(
    db: Session, doctor: Doctor, start_at: datetime, clinic_timezone: str,
) -> SessionArrivalRead:
    """Record when the doctor left; the first time recorded is kept."""
    sessions = todays_sessions(db, doctor.id, clinic_timezone, include_ended=True)
    if not any(start == start_at for start, _ in sessions):
        raise NotFoundError("Session today")
    arrival = db.scalar(select(SessionArrival).where(
        SessionArrival.doctor_id == doctor.id, SessionArrival.session_start == start_at,
    ))
    if arrival is None:
        raise ConflictError("Mark the doctor as arrived first.")
    if arrival.left_at is None:
        if db.scalar(select(Visit.id).join(Visit.appointment).where(
            Visit.doctor_id == doctor.id, Visit.status == "in_progress", Appointment.start_at == start_at,
        )):
            raise ConflictError("A patient is still with the doctor. Complete that visit first.")
        arrival.left_at = datetime.now(timezone.utc)
        db.commit()
    return _attendance_read(arrival)
