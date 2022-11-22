from typing import Self, Any

from pydantic import BaseModel, Field
from telegram import Message
from telegram.ext import Application

from app.utils import get_logger, get_settings, get_repository

__all__ = ["User"]

logger = get_logger(__file__)
settings = get_settings()
repo: Any


class User(BaseModel):
    telegram_id: int
    context: dict = Field(default_factory=dict)
    inputs: dict[str, str] = Field(default_factory=dict)
    interpreter: Any = None

    async def save(self):
        await repo.save_user(self)

    def expect(self, **inputs):
        self.inputs.update({v: k for k, v in inputs.items()})

    def accept(self, name: str):
        for key in [k for k, v in self.inputs.items() if v == name]:
            del self.inputs[key]

    def parse_input(self, message: Message) -> tuple[str, Any] | None:
        if not (text := message.text):
            return
        if target := self.inputs.get("integer"):
            try:
                integer = int(text)
            except ValueError:
                pass
            else:
                return target, integer

        if target := self.inputs.get("text"):
            return target, text

    @classmethod
    async def load(cls, telegram_id: int, app: Application) -> Self:
        global repo
        repo = get_repository()
        return await repo.load_user(telegram_id, app)
