from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from app.models import Content
from app.utils import get_settings

__all__ = ["Option"]

settings = get_settings()


class Option(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    bot: UUID = settings.bot.id
    name: str
    emoji: str = ""
    label: str = ""
    content: Content

    row: int
    column: int

    is_active: bool = Field(default=False, exclude=True)
    is_dummy: bool = Field(default=False, exclude=True)

    def __init__(self, **kwargs):
        if "content" not in kwargs:
            kwargs["content"] = Content(type="text", text=kwargs["name"])
        super().__init__(**kwargs)

    def __str__(self):
        prefix = f"{self.prefix} " if self.prefix else ""
        return f"{prefix}{self.name}"

    def __len__(self):
        return len(self.name) + 2

    @property
    def prefix(self):
        if self.is_active:
            return "✅"
        return self.emoji
