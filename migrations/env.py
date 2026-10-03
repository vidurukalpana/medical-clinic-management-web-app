"""Alembic environment for the clinic database configured by CLINIC_DATABASE_URL."""
from logging.config import fileConfig

from alembic import context
from sqlalchemy import Connection, create_engine

import app.models  # noqa: F401  Register all models on Base.metadata.
from app.core.config import get_settings
from app.db.base import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata

# Left behind in databases from before Alembic. They are removed only on purpose
# (`python -m app.db.initialize --purge-clinical-data`), so autogenerate must not drop them.
LEGACY_TABLES = {"doctor_working_hours"}
LEGACY_COLUMNS = {
    ("appointments", "reason"),
    ("doctor_unavailability", "unavailable_date"),
    ("doctor_unavailability", "created_at"),
    ("doctor_unavailability", "updated_at"),
    ("patients", "sex"),
    ("visits", "presenting_complaint"),
    ("visits", "diagnosis"),
    ("visits", "clinical_notes"),
    ("visits", "treatment_plan"),
}


def include_object(obj, name, type_, reflected, compare_to) -> bool:
    if not reflected or compare_to is not None:
        return True
    if type_ == "table":
        return name not in LEGACY_TABLES
    if type_ in ("column", "index", "unique_constraint", "foreign_key_constraint"):
        return obj.table.name not in LEGACY_TABLES and (obj.table.name, name) not in LEGACY_COLUMNS
    return True


def run_migrations_offline() -> None:
    """Print the migration SQL instead of running it (`alembic upgrade head --sql`)."""
    context.configure(
        url=get_settings().database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # The app passes its own connection, so startup and tests migrate their own engine.
    connection = config.attributes.get("connection")
    if connection is not None:
        run_migrations(connection)
        return

    engine = create_engine(get_settings().database_url)
    try:
        with engine.connect() as connection:
            run_migrations(connection)
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
