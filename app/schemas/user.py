from pydantic import BaseModel, ConfigDict

from app.models import UserRole


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    role: UserRole
    is_active: bool
