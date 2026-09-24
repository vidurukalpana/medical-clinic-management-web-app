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
