import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from app.utils import get_settings

__all__ = ["Suggestion"]

settings = get_settings()


class Suggestion(BaseModel):
    id: UUID
    bot: UUID = settings.bot_id
    owner: UUID
    candidate: UUID
    score: float
    context: Any
    date_created: datetime.datetime = datetime.datetime.utcnow()
