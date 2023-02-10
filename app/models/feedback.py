import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from app.utils import get_settings

__all__ = ["Feedback"]

settings = get_settings()


class Feedback(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    bot: UUID = settings.bot_id
    from_user: UUID
    to_user: UUID
    response: int
    context: dict = Field(default_factory=dict)
    date_created: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
