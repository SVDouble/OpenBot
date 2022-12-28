from functools import cached_property
from typing import Any, Self
from uuid import UUID, uuid4

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as SqlSession
from telegram import InlineKeyboardButton, Message
from telegram.ext import Application

from app.exceptions import ValidationError
from app.models import Content, User
from app.models.callback import Callback
from app.models.content_validator import ContentValidator
from app.models.option import Option
from app.models.question import Question
from app.profile import Session, get_profile
from app.utils import get_logger, get_repository, get_settings

__all__ = ["ProgramState"]

logger = get_logger(__file__)
settings = get_settings()
repo: Any | None = None


class ProgramState(BaseModel):
    class Config:
        keep_untouched = (cached_property,)

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

    @cached_property
    def _session(self) -> SqlSession:
        return Session()

    @cached_property
    def profile(self) -> Any:
        return get_profile(self._session, self.user.telegram_id)

    @classmethod
    async def load(cls, telegram_id: int, app: Application) -> Self:
        global repo
        repo = repo or get_repository()
        return await repo.load_state(telegram_id, app)

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        cache = self.__dict__
        if session := cache.pop("_session", None):
            session: SqlSession
            session.commit()
            session.close()
        cache.pop("profile", None)
        await repo.save_user(self)

    @property
    def total_choices(self) -> int:
        return len(self.selected_options) + len(self.created_options)

    @property
    def answer(self) -> Any:
        answer = {
            ContentValidator(
                type=self.question.content_type,
                value=option.content.value,
            ).get_content()
            for option in self.selected_options.values()
        } | self.created_options
        answer = {content.value for content in answer}
        return answer if self.question.allow_multiple_choices else answer.pop()

    def expect(self, **inputs):
        self.inputs.update(
            {
                k: v if isinstance(v, ContentValidator) else ContentValidator(type=v)
                for k, v in inputs.items()
            }
        )

    def release(self, *names: str):
        for name in names:
            self.inputs.pop(name, None)

    async def make_inline_button(self, name: str, **kwargs) -> InlineKeyboardButton:
        callback = Callback(
            user_telegram_id=self.user.telegram_id,
            data=kwargs.pop("data", name),
            **kwargs,
        )
        await repo.create_callback(self, callback)
        return InlineKeyboardButton(name, callback_data=str(callback.id))

    def clean_input(
        self, message: Message | None = None, callback: Callback | None = None
    ) -> tuple[str, Content] | None:
        if not (message is None) ^ (callback is None):
            raise RuntimeError("either message or callback must be specified")
        # noinspection PyUnresolvedReferences
        text = message.text if callback is None else callback.data

        if not text:
            return

        for target, constraint in sorted(self.inputs.items(), key=lambda item: item[1]):
            validator = ContentValidator(
                type=constraint.type, value=text, options=constraint.options
            )
            try:
                validator.clean()
            except ValidationError:
                continue
            else:
                return target, validator.get_content()

    async def save_answer(self):
        self.answers[self.question.label] = self.answer
        if trait := self.question.user_trait:
            setattr(self.profile, trait.column, self.answer)
