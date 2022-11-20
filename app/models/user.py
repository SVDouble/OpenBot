import pickle
from typing import Self, Any

from pydantic import BaseModel, Field
from telegram import Message
from telegram.ext import Application

from app.models import StateChart
from app.settings import get_settings
from app.utils import get_logger

__all__ = ["User"]

logger = get_logger(__file__)
settings = get_settings()

# TODO: replace with redis
storage: dict[int, bytes] = {}


class User(BaseModel):
    telegram_id: int
    context: dict = Field(default_factory=dict)
    inputs: dict[str, str] = Field(default_factory=dict)
    interpreter: Any = None

    async def save(self):
        storage[self.telegram_id] = pickle.dumps(self)

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
        from app.engine import UserInterpreter

        if pickled_user := storage.get(telegram_id):
            user = pickle.loads(pickled_user)
            user.interpreter.user = user
            user.interpreter.app = app
            return user
        user = User(telegram_id=telegram_id)
        statechart = StateChart.load(settings.user_statechart_source)
        user.interpreter = UserInterpreter(user, app, statechart)
        return user

    @classmethod
    async def get_active_user_ids(cls) -> list[int]:
        return list(storage.keys())
