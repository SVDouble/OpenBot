from functools import cached_property
from typing import Self, Any
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as SqlSession
from telegram import InlineKeyboardButton, Message
from telegram.ext import Application

from app.exceptions import ValidationError
from app.models import Content
from app.models.callback import Callback
from app.models.content_validator import ContentValidator
from app.models.option import Option
from app.models.question import Question
from app.profile import get_profile, Session
from app.utils import get_logger, get_settings, get_repository

__all__ = ["User"]

logger = get_logger(__file__)
settings = get_settings()
repo: Any | None = None


class User(BaseModel):
    class Config:
        keep_untouched = (cached_property,)

    telegram_id: int
    data: dict[str, Any] = Field(default_factory=dict)
    is_registered: bool = False

    inputs: dict[str, ContentValidator] = Field(default_factory=dict)
    question: Question | None = None
    selected_options: dict[UUID, Option] = Field(default_factory=dict)
    created_options: set[Content] = Field(default_factory=set)
    validate_answer: bool = False
    last_answer: Any | None = None
    is_reply_keyboard_set: bool = False

    interpreter: Any = None

    def __getitem__(self, item):
        return self.data[item]

    @cached_property
    def _session(self) -> SqlSession:
        return Session()

    @cached_property
    def profile(self) -> Any:
        return get_profile(self._session, self.telegram_id)

    @property
    def total_choices(self) -> int:
        return len(self.selected_options) + len(self.created_options)

    @property
    def answer(self) -> Any:
        answer = {
            ContentValidator(
                type=self.question.content_type, value=option.value or option.name
            )
            for option in self.selected_options.values()
        } | self.created_options
        answer = {content.payload for content in answer}
        return answer if self.question.allow_multiple_choices else answer.pop()

    async def save(self):
        await repo.save_user(self)

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
            user_telegram_id=self.telegram_id,
            data=kwargs.pop("data", name),
            **kwargs,
        )
        await callback.save()
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
        self.last_answer = self.answer
        if (field := self.question.field) is not None:
            self.data[field] = self.last_answer

    @classmethod
    async def load(cls, telegram_id: int, app: Application) -> Self:
        global repo
        repo = repo or get_repository()
        return await repo.load_user(telegram_id, app)

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        cache = self.__dict__
        if session := cache.pop("_session", None):
            session: SqlSession
            session.commit()
            session.close()
        cache.pop("profile", None)
        await self.save()
