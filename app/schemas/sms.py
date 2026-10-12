from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class SmsMessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    appointment_id: int | None
    kind: Literal["confirmation", "reminder"]
    phone: str
    body: str
    status: Literal["queued", "sent", "failed", "logged"]
    error: str | None
    created_at: datetime
    sent_at: datetime | None


class SmsOutboxPage(BaseModel):
    items: list[SmsMessageRead]
    total: int
    offset: int
    limit: int
    # "outbox" means messages are recorded but not sent.
    provider: str
