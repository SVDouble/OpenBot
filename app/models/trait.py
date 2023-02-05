import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.content import ContentType
from app.utils import get_settings

__all__ = ["Trait"]

settings = get_settings()


class Trait(BaseModel):
    id: UUID
    bot: UUID = settings.bot_id
    name: str
    emoji: str = ""
    is_visible: bool = True
    is_editable: bool = True
    is_sensitive: bool = True

    type: ContentType
    column: str
    is_multivalued: bool = False

    date_created: datetime.datetime = Field(datetime.datetime.utcnow)
