from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from app.models.content import Content
from app.models.option import Option

__all__ = ["Question"]


class Question(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str
    emoji: str = ""

    field: str | None = None
    content_type: Content.Type

    allow_skipping: bool = False
    allow_arbitrary_input: bool = False
    allow_multiple_choices: bool = False
    allow_empty_answers: bool = False

    text_skip: str = "Пропустить вопрос"
    text_error: str | None = None

    options: list[list[Option]] = Field(default_factory=list)

    def __str__(self):
        emoji = f"{self.emoji} " if self.emoji else ""
        return f"[{self.id.hex[:8]}] {emoji}{self.name}"
