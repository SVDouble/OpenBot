import datetime
from functools import cached_property
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, ConfigDict

from app.utils import get_logger, get_settings

__all__ = ["State"]

logger = get_logger(__file__)
settings = get_settings()


class State(BaseModel):
    model_config = ConfigDict(ignored_types=(cached_property,))

    id: UUID = Field(default_factory=uuid4)
    bot: UUID = settings.bot_id
    user: UUID
    statechart: UUID
    data: dict = Field(default_factory=dict)

    active_question: UUID | None = None
    active_states: set[str] = Field(default_factory=set)

    date_created: datetime.datetime = datetime.datetime.utcnow()
    date_updated: datetime.datetime = datetime.datetime.utcnow()
