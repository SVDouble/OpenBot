import datetime
from enum import Enum, unique
from typing import Any
from uuid import UUID

from pydantic import BaseModel

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


_float_type = float


class Content(BaseModel):
    id: UUID | None = None
    bot: UUID = settings.bot_id
    owner: UUID | None = None
    type: ContentType
    description: str | None = None
    metadata: dict | None = None
    date_created: datetime.datetime = datetime.datetime.utcnow()

    text: str | None = None
    boolean: bool | None = None
    integer: int | None = None
    float: _float_type | None = None
    number_range: dict | None = None
    date: datetime.datetime | None = None
    date_range: dict | None = None
    location: dict | None = None
    tag: UUID | None = None
    city: UUID | None = None
    university: UUID | None = None
    photo: str | None = None
    photo_url: str | None = None
    file: str | None = None
    file_url: str | None = None

    @property
    def value(self) -> Any | None:
        fallback = None
        if self.type in (ContentType.PHOTO, ContentType.FILE):
            fallback = self.metadata.get("file_id")
        value = getattr(self, self.type.value)
        if value is None:
            value = fallback
        return value

    def __repr__(self) -> str:
        return f"('{self.type.value}', {self.value!r})"
