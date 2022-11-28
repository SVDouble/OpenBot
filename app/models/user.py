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

    inputs: dict[str, Content] = Field(default_factory=dict)
    question: Question | None = None
    selected_options: dict[UUID, Option] = Field(default_factory=dict)
    created_options: set[Content] = Field(default_factory=set)

    is_registered: bool = False
    home_message: str | None = None

    interpreter: Any = None

    async def save(self):
        await repo.save_user(self)

    def expect(self, **inputs):
        self.inputs.update(
            {
                k: v if isinstance(v, Content) else Content(type=v)
                for k, v in inputs.items()
            }
        )

    def accept(self, name: str):
        del self.inputs[name]

    async def make_inline_button(
        self, name: str, target: str = None, button_kwargs: dict = None, **kwargs
    ) -> InlineKeyboardButton:
        callback = Callback(
            user_telegram_id=self.telegram_id, target=target or name, **kwargs
        )
        await callback.save()
        return InlineKeyboardButton(name, callback_data=callback.id, **button_kwargs)

    def clean_input(self, message: Message) -> tuple[str, Any] | None:
        if not (text := message.text):
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

    @classmethod
    async def load(cls, telegram_id: int, app: Application) -> Self:
        global repo
        repo = repo or get_repository()
        return await repo.load_user(telegram_id, app)
