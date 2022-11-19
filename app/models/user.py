import pickle
from typing import Self, Any

from pydantic import BaseModel, Field
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
    expected_input: list[str] = Field(default_factory=list)
    engine: Any = None

    async def save(self):
        pickle.dumps(self.engine.interpreter)
        storage[self.telegram_id] = pickle.dumps(self)

    @classmethod
    async def load(cls, telegram_id: int, app: Application) -> Self:
        from app.engine import UserEngine

        if pickled_user := storage.get(telegram_id):
            return pickle.loads(pickled_user)
        user = User(telegram_id=telegram_id)
        statechart = StateChart.load(settings.user_statechart_source)
        user.engine = UserEngine(user, app, statechart)
        return user

    @classmethod
    async def get_active_user_ids(cls) -> list[int]:
        return list(storage.keys())
