from collections.abc import Generator
from uuid import uuid4

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, create_engine, inspect, text

from app.db.base import Base
from app.db.initialize import MIGRATIONS_DIRECTORY, migrate_database


@pytest.fixture
def schema_engine(test_settings) -> Generator[Engine]:
    """An engine whose tables live in a new, empty schema."""
    schema_name = f"clinic_migration_test_{uuid4().hex}"
    admin_engine = create_engine(test_settings.database_url)
    with admin_engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema_name}"'))
    engine = create_engine(
        test_settings.database_url,
        connect_args={"options": f"-csearch_path={schema_name}"},
    )
    try:
        yield engine
    finally:
        engine.dispose()
        with admin_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema_name}" CASCADE'))
        admin_engine.dispose()


def head_revision() -> str:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIRECTORY))
    return ScriptDirectory.from_config(config).get_current_head()


def current_revision(engine: Engine) -> str | None:
    with engine.connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()


def schema_differences(engine: Engine) -> list:
    with engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"compare_type": True})
        differences = compare_metadata(context, Base.metadata)
        # Autogenerate ignores standalone sequences, so check them separately.
        existing_sequences = set(inspect(connection).get_sequence_names())
        differences += [
            ("missing_sequence", name) for name in Base.metadata._sequences if name not in existing_sequences
        ]
        return differences


def test_migrations_create_the_schema_the_models_describe(schema_engine):
    migrate_database(schema_engine, "Asia/Colombo")

    assert current_revision(schema_engine) == head_revision()
    # A non-empty list means a model changed without a migration: run `alembic revision --autogenerate`.
    assert schema_differences(schema_engine) == []


def test_migrations_downgrade_and_upgrade_again(schema_engine):
    migrate_database(schema_engine, "Asia/Colombo")
    with schema_engine.begin() as connection:
        config = Config()
        config.set_main_option("script_location", str(MIGRATIONS_DIRECTORY))
        config.attributes["connection"] = connection
        command.downgrade(config, "base")
        assert set(inspect(connection).get_table_names()) == {"alembic_version"}

    migrate_database(schema_engine, "Asia/Colombo")
    assert schema_differences(schema_engine) == []


def test_database_created_before_alembic_is_upgraded_and_stamped(schema_engine):
    # An older release: `create_all` tables without the guest token column or Alembic history.
    Base.metadata.create_all(bind=schema_engine)
    with schema_engine.begin() as connection:
        connection.execute(text("ALTER TABLE appointments DROP COLUMN guest_token_hash"))
        connection.execute(text("DROP TABLE auth_sessions"))

    migrate_database(schema_engine, "Asia/Colombo")
    migrate_database(schema_engine, "Asia/Colombo")

    assert current_revision(schema_engine) == head_revision()
    assert schema_differences(schema_engine) == []
