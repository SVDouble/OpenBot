from functools import cached_property
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from app.models.content import Content
from app.models.content_validator import ContentValidator
from app.models.option import Option
from app.models.question import Question
from app.models.state import State
from app.models.suggestion import Suggestion
from app.models.user import User
from app.utils import get_logger, get_settings

__all__ = ["Cache", "InterpreterCache"]

logger = get_logger(__file__)
settings = get_settings()


class InterpreterCache(BaseModel):
    class Config:
        allow_population_by_field_name = True

    ignore_contract: bool = Field(alias="_ignore_contract")
    # shows whether the statechart was executed at least once
    initialized: bool = Field(alias="_initialized")
    time: float = Field(alias="_time")
    memory: dict[str, float] = Field(alias="_memory")
    configuration: set[str] = Field(alias="_configuration")
    entry_time: dict[str, float] = Field(alias="_entry_time")
    idle_time: dict[str, float] = Field(alias="_idle_time")
    sent_events: list = Field(alias="_sent_events")
    internal_queue: list = Field(alias="_internal_queue")
    external_queue: list = Field(alias="_external_queue")
    is_initialized: bool = Field(alias="_is_initialized")


class Cache(BaseModel):
    class Config:
        keep_untouched = (cached_property,)

    id: UUID = Field(default_factory=uuid4)
    user: User

    # survey-related
    question: Question | None = None
    answers: dict[str, dict] = Field(default_factory=dict)
    inputs: dict[str, ContentValidator] = Field(default_factory=dict)
    selected_options: dict[UUID, Option] = Field(default_factory=dict)
    created_options: list[Content] = Field(default_factory=list)
    validate_answer: bool = False
    is_reply_keyboard_set: bool = False

    # matching-related
    suggestion: Suggestion | None = None

    # service
    interpreter: Any = Field(default_factory=None, exclude=True)
    interpreter_cache: InterpreterCache | None = None

    @property
    def total_choices(self) -> int:
        return len(self.selected_options) + len(self.created_options)

    @property
    def profile(self) -> Any:
        return self.interpreter and self.interpreter.context.get("profile")

    @cached_property
    def context(self) -> dict:
        return {}

    def modify_state(self, state: State = None) -> State:
        self.interpreter_cache = self.interpreter.state_cache
        state.data = self.dict(exclude_none=True)
        state.active_question = self.question and self.question.id
        state.active_states = self.interpreter_cache.configuration
        return state

    def __getstate__(self):
        if self.interpreter:
            self.interpreter_cache = self.interpreter.state_cache
        state = super().__getstate__()
        data = state["__dict__"].copy()
        del data["interpreter"]
        state["__dict__"] = data
        return state
