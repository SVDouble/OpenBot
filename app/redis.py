import pickle
from typing import Any

import redis.asyncio as redis

__all__ = ["Repository"]

from telegram.ext import Application

from app.models import User, StateChart
from app.utils import get_settings

settings = get_settings()


def init_redis_client(decode_responses=True) -> redis.Redis:
    return redis.from_url(
        settings.redis_url,
        encoding="utf-8",
        db=settings.redis_db,
        decode_responses=decode_responses,
    )


class Repository:
    def __init__(self):
        self.db = init_redis_client()
        self.raw_db = init_redis_client(decode_responses=False)

    async def get_pickle(self, key: str) -> Any | None:
        if data := await self.raw_db.get(key):
            return pickle.loads(data)

    async def set_pickle(self, key: str, value: Any):
        await self.raw_db.set(key, pickle.dumps(value))

    async def save_user(self, user: User):
        await self.set_pickle(f"user:{user.telegram_id}", user)
        await self.db.sadd("users", user.telegram_id)

    async def load_user(self, telegram_id: int, app: Application) -> User:
        from app.engine import UserInterpreter

        if user := await self.get_pickle(f"user:{telegram_id}"):
            user.interpreter.user = user
            user.interpreter.app = app
            return user
        user = User(telegram_id=telegram_id)
        statechart = StateChart.load(settings.user_statechart_source)
        user.interpreter = UserInterpreter(user, app, statechart)
        await user.save()
        return user

    async def get_user_ids(self) -> set[int]:
        return set(int(uid) for uid in await self.db.smembers("users"))
