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
