from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from app.models.content import ContentType
from app.models.option import Option
from app.models.trait import Trait
from app.utils import get_settings

__all__ = ["Question"]

settings = get_settings()


class Question(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    bot: UUID = settings.bot_id
    name: str
    emoji: str = ""
    label: str

    content_type: ContentType
    user_trait: Trait | None = None

    allow_skipping: bool = False
    allow_arbitrary_input: bool = False
    allow_multiple_choices: bool = False
    allow_empty_answers: bool = False
    is_rhetorical: bool = False

    text_skip: str = "Пропустить вопрос"
    text_error: str | None = None

    options: list[Option] = Field(default_factory=list)

    def __str__(self):
        emoji = f"{self.emoji} " if self.emoji else ""
        return f"[{self.id.hex[:8]}] {emoji}{self.name}"
