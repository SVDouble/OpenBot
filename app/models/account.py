import datetime
from uuid import UUID

from pydantic import BaseModel

__all__ = ["Account"]


class Account(BaseModel):
    id: UUID
    username: str | None = None
    telegram_id: int
    is_active: bool
    date_joined: datetime.datetime
