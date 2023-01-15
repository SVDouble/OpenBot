from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from app.models.content import Content
from app.models.content_validator import ContentValidator
from app.models.option import Option
from app.models.question import Question
from app.models.user import User
from app.utils import get_logger, get_settings

__all__ = ["ProgramState"]

logger = get_logger(__file__)
settings = get_settings()


class ProgramState(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    user: User
    interpreter_state: dict = Field(default_factory=dict)
    answers: dict[str, Any] = Field(default_factory=dict)

    inputs: dict[str, ContentValidator] = Field(default_factory=dict)
    question: Question | None = None
    selected_options: dict[UUID, Option] = Field(default_factory=dict)
    created_options: set[Content] = Field(default_factory=set)
    validate_answer: bool = False
    is_reply_keyboard_set: bool = False

    interpreter: Any = Field(default_factory=None, exclude=True)

    def __getstate__(self):
        if self.interpreter:
            self.interpreter_state = self.interpreter.state
        state = super().__getstate__()
        data = state["__dict__"].copy()
        del data["interpreter"]
        state["__dict__"] = data
        return state

    def __getitem__(self, item):
        return self.answers[item]
