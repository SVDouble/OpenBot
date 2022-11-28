import pickle
from typing import Any
from uuid import UUID

import redis.asyncio as redis

__all__ = ["Repository"]

from telegram.ext import Application

from app.models import User, StateChart, Callback
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

    async def delete_pickle(self, key: str):
        await self.raw_db.delete(key)

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
        await user.interpreter.dispatch_event("init")
        await user.save()
        return user

    async def remove_user(self, telegram_id: int):
        await self.db.delete(f"user:{telegram_id}")

    async def get_user_ids(self) -> set[int]:
        return set(int(uid) for uid in await self.db.smembers("users"))

    async def create_callback(self, callback: Callback, user: int | User):
        telegram_id = user if isinstance(user, int) else user.telegram_id
        await self.set_pickle(f"callback:{telegram_id}:{callback.id}", callback)

    async def get_callback(
        self, callback_id: UUID | str, user: int | User
    ) -> Callback | None:
        telegram_id = user if isinstance(user, int) else user.telegram_id
        return await self.get_pickle(f"callback:{telegram_id}:{callback_id}")

    async def remove_callback(self, callback_id: UUID | str, user: int | User):
        telegram_id = user if isinstance(user, int) else user.telegram_id
        await self.delete_pickle(f"callback:{telegram_id}:{callback_id}")
