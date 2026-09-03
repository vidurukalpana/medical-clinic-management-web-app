"""User account services."""

from sqlalchemy.orm import Session

from app.errors import NotFoundError
from app.models import User


def get_user(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise NotFoundError("User")
    return user
