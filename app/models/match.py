import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.utils import get_settings

__all__ = ["Match"]

settings = get_settings()


class Match(BaseModel):
    id: UUID
    bot: UUID = settings.bot_id
    users: list[UUID]
    date_created: datetime.datetime = Field(datetime.datetime.utcnow)
    date_delivered: datetime.datetime | None = None
