from typing import Self, Any
from uuid import UUID

from pydantic import BaseModel, Field
from telegram import InlineKeyboardButton, Message
from telegram.ext import Application

from app.exceptions import ValidationError
from app.models.callback import Callback
from app.models.content import Content
from app.models.option import Option
from app.models.question import Question
from app.utils import get_logger, get_settings, get_repository

__all__ = ["User"]

logger = get_logger(__file__)
settings = get_settings()
repo: Any | None = None


class User(BaseModel):
    telegram_id: int
    data: dict[str, Any] = Field(default_factory=dict)

    inputs: dict[str, Content] = Field(default_factory=dict)
    question: Question | None = None
    selected_options: dict[UUID, Option] = Field(default_factory=dict)
    created_options: set[Content] = Field(default_factory=set)
    validate_answer: bool = False
    last_answer: Any | None = None

    is_registered: bool = False
    home_message: str | None = None

    interpreter: Any = None

    def __getitem__(self, item):
        return self.data[item]

    @property
    def answer(self) -> Any:
        answer = {
            Content(type=self.question.expect, value=option.value or option.name)
            for option in self.selected_options.values()
        } | self.created_options
        answer = {content.payload for content in answer}
        return answer if self.question.is_multiple_choice else answer.pop()

    async def save(self):
        await repo.save_user(self)

    def expect(self, **inputs):
        self.inputs.update(
            {
                k: v if isinstance(v, Content) else Content(type=v)
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
    ) -> tuple[str, Any] | None:
        if not (message is None) ^ (callback is None):
            raise RuntimeError("either message or callback must be specified")
        # noinspection PyUnresolvedReferences
        text = message.text if callback is None else callback.data

        if not text:
            return

        for target, constraint in sorted(self.inputs.items(), key=lambda item: item[1]):
            content = Content(
                type=constraint.type, value=text, options=constraint.options
            )
            try:
                content.clean()
            except ValidationError:
                continue
            else:
                return target, content

    async def save_answer(self):
        self.last_answer = self.answer
        if (field := self.question.field) is not None:
            self.data[field] = self.last_answer

    @classmethod
    async def load(cls, telegram_id: int, app: Application) -> Self:
        global repo
        repo = repo or get_repository()
        return await repo.load_user(telegram_id, app)
