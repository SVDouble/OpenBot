from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from app.models.content import Content
from app.models.option import Option

__all__ = ["Question"]


class Question(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    type: (
        Literal["SingleChoiceQuestion"]
        | Literal["MultipleChoiceQuestion"]
        | Literal["OpenEndedQuestion"]
    )
    name: str
    expect: Content.Type
    emoji: str = ""
    label: str = ""
    is_skippable: bool = False
    is_customizable: bool = False
    accept_empty_answers: bool = False

    text_action_create_option: str = "Добавить вариант"
    text_prompt_create_option: str = "Введите свой вариант"
    text_action_skip_question: str = "Пропустить вопрос"

    options: list[Option]

    def __str__(self):
        emoji = f"{self.emoji} " if self.emoji else ""
        return f"[{self.id.hex[:8]}] {emoji}{self.name}"

    @property
    def is_single_choice(self) -> bool:
        return self.type == "SingleChoiceQuestion"

    @property
    def is_multiple_choice(self) -> bool:
        return self.type == "MultipleChoiceQuestion"

    @property
    def is_open_ended(self) -> bool:
        return self.type == "OpenEndedQuestion"
