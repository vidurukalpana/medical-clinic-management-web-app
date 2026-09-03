"""Application health services."""

from sqlalchemy import text
from sqlalchemy.orm import Session


def verify_database_connection(db: Session) -> None:
    db.execute(text("SELECT 1"))
