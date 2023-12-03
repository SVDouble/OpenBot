import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.content import Content
from app.utils import get_settings

__all__ = ["Answer"]

settings = get_settings()


class Answer(BaseModel):
    id: UUID | None = None
    bot: UUID = settings.bot_id
    owner: UUID
    question: UUID
    user_trait: UUID

    is_question_skipped: bool = False
    selected_options: list[UUID] = Field(default_factory=list)
    created_options: list[Content] = Field(default_factory=list)
    date_created: datetime.datetime | None = None
