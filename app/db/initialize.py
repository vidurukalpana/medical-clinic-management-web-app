from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

import app.models  # Register all SQLAlchemy models before creating tables.
from app.core.config import Settings
from app.db.base import Base
from app.db.seed import seed_initial_accounts


def initialize_database(database_engine: Engine, settings: Settings) -> None:
    Base.metadata.create_all(bind=database_engine)
    with Session(database_engine) as db:
        seed_initial_accounts(db, settings)
    with database_engine.connect() as connection:
        connection.execute(text("SELECT 1"))


def upgrade_booking_schema(database_engine: Engine, *, purge_clinical_data: bool = False) -> None:
    """Upgrade existing tables in place; clinical deletion requires an explicit flag."""
    with database_engine.begin() as connection:
        connection.execute(text("ALTER TABLE patients ALTER COLUMN date_of_birth DROP NOT NULL"))
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
