from sqlalchemy import Connection, Engine, text
from sqlalchemy.orm import Session

import app.models  # Register all SQLAlchemy models before creating tables.
from app.core.config import Settings, get_settings
from app.db.base import Base
from app.db.seed import seed_initial_accounts


def initialize_database(database_engine: Engine, settings: Settings) -> None:
    Base.metadata.create_all(bind=database_engine)
    with Session(database_engine) as db:
        seed_initial_accounts(db, settings)
    with database_engine.connect() as connection:
        connection.execute(text("SELECT 1"))


def _has_column(connection: Connection, table: str, column: str) -> bool:
    return connection.execute(text(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_schema = current_schema() AND table_name = :table AND column_name = :column"
    ), {"table": table, "column": column}).first() is not None


def _upgrade_patient_gender(connection: Connection) -> None:
    """Replace the legacy required `sex` column with the optional-value `gender` column."""
    if _has_column(connection, "patients", "gender"):
        return
    connection.execute(text("ALTER TABLE patients ADD COLUMN gender VARCHAR(20)"))
    if _has_column(connection, "patients", "sex"):
        # Enum values are stored by member name, matching the other enum columns.
        connection.execute(text("""
            UPDATE patients SET gender = CASE upper(trim(sex))
                WHEN 'FEMALE' THEN 'FEMALE' WHEN 'F' THEN 'FEMALE'
                WHEN 'MALE' THEN 'MALE' WHEN 'M' THEN 'MALE'
                WHEN 'OTHER' THEN 'OTHER'
                ELSE 'NOT_SPECIFIED' END
        """))
        # Keep the legacy values, but stop requiring them for new patients.
        connection.execute(text("ALTER TABLE patients ALTER COLUMN sex DROP NOT NULL"))
    connection.execute(text("UPDATE patients SET gender = 'NOT_SPECIFIED' WHERE gender IS NULL"))
    connection.execute(text("ALTER TABLE patients ALTER COLUMN gender SET NOT NULL"))


def _upgrade_doctor_unavailability(connection: Connection, timezone: str) -> None:
    """Move whole-day `unavailable_date` rows to the `start_at`/`end_at` period columns."""
    if _has_column(connection, "doctor_unavailability", "start_at"):
        return
    connection.execute(text(
        "ALTER TABLE doctor_unavailability "
        "ADD COLUMN start_at TIMESTAMP WITH TIME ZONE, ADD COLUMN end_at TIMESTAMP WITH TIME ZONE"
    ))
    if _has_column(connection, "doctor_unavailability", "unavailable_date"):
        # A legacy date blocked the whole clinic-local day.
        connection.execute(text("""
            UPDATE doctor_unavailability
            SET start_at = unavailable_date::timestamp AT TIME ZONE :tz,
                end_at = (unavailable_date + 1)::timestamp AT TIME ZONE :tz
        """), {"tz": timezone})
        connection.execute(text(
            "ALTER TABLE doctor_unavailability DROP CONSTRAINT IF EXISTS uq_doctor_unavailability_doctor_date"
        ))
        connection.execute(text("ALTER TABLE doctor_unavailability ALTER COLUMN unavailable_date DROP NOT NULL"))
    for column in ("created_at", "updated_at"):
        # Legacy audit columns are not written by the current model.
        if _has_column(connection, "doctor_unavailability", column):
            connection.execute(text(
                f"ALTER TABLE doctor_unavailability ALTER COLUMN {column} SET DEFAULT now()"
            ))
    connection.execute(text(
        "ALTER TABLE doctor_unavailability ALTER COLUMN start_at SET NOT NULL, ALTER COLUMN end_at SET NOT NULL"
    ))
    connection.execute(text(
        "ALTER TABLE doctor_unavailability ADD CONSTRAINT ck_doctor_unavailability_time_order "
        "CHECK (start_at < end_at)"
    ))


def _upgrade_session_capacity(connection: Connection) -> None:
    """Replace per-slot minutes with a per-session patient limit of the same size."""
    if _has_column(connection, "availability", "max_patients"):
        return
    connection.execute(text("ALTER TABLE availability ADD COLUMN max_patients INTEGER NOT NULL DEFAULT 20"))
    if _has_column(connection, "availability", "slot_duration_minutes"):
        connection.execute(text("""
            UPDATE availability SET max_patients = LEAST(200, GREATEST(1, floor(
                extract(epoch FROM end_time - start_time) / 60 / slot_duration_minutes
            )::int))
        """))
        # Keep the legacy values, but stop requiring them for new sessions.
        connection.execute(text("ALTER TABLE availability ALTER COLUMN slot_duration_minutes DROP NOT NULL"))
    connection.execute(text(
        "ALTER TABLE availability ADD CONSTRAINT ck_availability_max_patients "
        "CHECK (max_patients BETWEEN 1 AND 200)"
    ))


def _upgrade_reserved_places(connection: Connection) -> None:
    """Add the per-session count of places kept for walk-ins and reception."""
    if _has_column(connection, "availability", "reserved_places"):
        return
    connection.execute(text("ALTER TABLE availability ADD COLUMN reserved_places INTEGER NOT NULL DEFAULT 0"))
    connection.execute(text(
        "ALTER TABLE availability ADD CONSTRAINT ck_availability_reserved_places "
        "CHECK (reserved_places BETWEEN 0 AND max_patients)"
    ))


def _upgrade_doctor_profiles(connection: Connection) -> None:
    """Add the optional public profile columns shown to patients."""
    for column, kind in (("specialty", "VARCHAR(80)"), ("qualifications", "VARCHAR(200)"),
                         ("languages", "VARCHAR(120)"), ("bio", "VARCHAR(500)")):
        connection.execute(text(f"ALTER TABLE doctors ADD COLUMN IF NOT EXISTS {column} {kind}"))
    if not _has_column(connection, "doctors", "consultation_fee"):
        connection.execute(text("ALTER TABLE doctors ADD COLUMN consultation_fee INTEGER"))
        connection.execute(text(
            "ALTER TABLE doctors ADD CONSTRAINT ck_doctor_consultation_fee CHECK (consultation_fee >= 0)"
        ))


def _upgrade_appointment_numbers(connection: Connection, timezone: str) -> None:
    """Move upcoming slot bookings into their session and number them in their old time order."""
    if _has_column(connection, "appointments", "appointment_number"):
        return
    connection.execute(text("DROP INDEX IF EXISTS uq_appointment_doctor_start"))
    connection.execute(text("ALTER TABLE appointments ADD COLUMN appointment_number INTEGER"))
    connection.execute(text("""
        WITH moved AS (
            SELECT a.id, a.doctor_id, a.status, a.start_at AS old_start,
                   COALESCE(s.session_start, a.start_at) AS new_start,
                   COALESCE(s.session_end, a.end_at) AS new_end
            FROM appointments a
            LEFT JOIN LATERAL (
                SELECT ((a.start_at AT TIME ZONE :tz)::date + av.start_time) AT TIME ZONE :tz AS session_start,
                       ((a.start_at AT TIME ZONE :tz)::date + av.end_time) AT TIME ZONE :tz AS session_end
                FROM availability av
                WHERE av.doctor_id = a.doctor_id AND av.is_active
                  AND av.weekday = extract(isodow FROM a.start_at AT TIME ZONE :tz) - 1
                  AND (a.start_at AT TIME ZONE :tz)::time >= av.start_time
                  AND (a.start_at AT TIME ZONE :tz)::time < av.end_time
                LIMIT 1
            ) s ON a.status = 'scheduled' AND a.end_at > now()
        ), numbered AS (
            SELECT id, new_start, new_end, row_number() OVER (
                PARTITION BY doctor_id, new_start
                ORDER BY status = 'cancelled', old_start, id
            ) AS number
            FROM moved
        )
        UPDATE appointments a
        SET start_at = n.new_start, end_at = n.new_end, appointment_number = n.number
        FROM numbered n WHERE a.id = n.id
    """), {"tz": timezone})
    connection.execute(text("ALTER TABLE appointments ALTER COLUMN appointment_number SET NOT NULL"))
    connection.execute(text(
        "ALTER TABLE appointments ADD CONSTRAINT ck_appointment_number CHECK (appointment_number > 0)"
    ))
    connection.execute(text(
        "CREATE UNIQUE INDEX uq_appointment_session_number "
        "ON appointments (doctor_id, start_at, appointment_number) WHERE status <> 'cancelled'"
    ))


def upgrade_booking_schema(
    database_engine: Engine, *, purge_clinical_data: bool = False, timezone: str | None = None,
) -> None:
    """Upgrade existing tables in place; clinical deletion requires an explicit flag."""
    timezone = timezone or get_settings().timezone
    with database_engine.begin() as connection:
        connection.execute(text("ALTER TABLE patients ALTER COLUMN date_of_birth DROP NOT NULL"))
        _upgrade_patient_gender(connection)
        _upgrade_doctor_unavailability(connection, timezone)
        connection.execute(text("ALTER TABLE appointments ADD COLUMN IF NOT EXISTS guest_token_hash VARCHAR(64)"))
        connection.execute(text("ALTER TABLE appointments ADD COLUMN IF NOT EXISTS booked_by_user_id INTEGER REFERENCES users(id)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_appointments_booked_by_user_id ON appointments (booked_by_user_id)"))
        _upgrade_session_capacity(connection)
        _upgrade_reserved_places(connection)
        _upgrade_doctor_profiles(connection)
        _upgrade_appointment_numbers(connection, timezone)
        if purge_clinical_data:
            connection.execute(text("ALTER TABLE appointments DROP COLUMN IF EXISTS reason"))
            for column in ("presenting_complaint", "diagnosis", "clinical_notes", "treatment_plan"):
                connection.execute(text(f"ALTER TABLE visits DROP COLUMN IF EXISTS {column}"))


if __name__ == "__main__":
    import argparse
    from app.db.session import engine

    parser = argparse.ArgumentParser(description="Upgrade an existing clinic database in place.")
    parser.add_argument("--purge-clinical-data", action="store_true",
                        help="Permanently remove legacy appointment reasons and clinical visit fields.")
    arguments = parser.parse_args()
    upgrade_booking_schema(engine, purge_clinical_data=arguments.purge_clinical_data)
