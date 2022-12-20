import datetime
from enum import unique, Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Json

from app.utils import get_settings

__all__ = ["Content", "ContentType"]

settings = get_settings()


@unique
class ContentType(str, Enum):
    TEXT = "text"
    BOOLEAN = "boolean"
    INTEGER = "integer"
    FLOAT = "float"
    NUMBER_RANGE = "number_range"
    DATE = "date"
    DATE_RANGE = "date_range"
    LOCATION = "location"
    TAG = "tag"
    CITY = "city"
    UNIVERSITY = "university"
    PHOTO = "photo"
    FILE = "file"


class Content(BaseModel):
    bot: UUID = settings.bot_uuid
    owner: UUID
    type: ContentType
    metadata: Json | None = None
    date_created: datetime.datetime = datetime.datetime.utcnow()

    text: str | None = None
    boolean: bool | None = None
    integer: int | None = None
    float: float | None = None
    number_range: dict | None = None
    date: datetime.datetime | None = None
    date_range: dict | None = None
    location: dict | None = None
    tag: UUID | None = None
    city: UUID | None = None
    university: UUID | None = None
    photo: str | None = None
    file: str | None = None

    @property
    def value(self) -> Any | None:
        return getattr(self, self.type.value)
