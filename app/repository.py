import pickle
from typing import Any
from uuid import UUID

import httpx
import redis.asyncio as redis

__all__ = ["Repository"]

from authlib.integrations.httpx_client import AsyncOAuth2Client
from telegram.ext import Application

from app.models import Callback, Statechart, User
from app.utils import get_settings, get_logger

settings = get_settings()
logger = get_logger(__file__)


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
        self.httpx = AsyncOAuth2Client(
            token_endpoint="/token/refresh/",
            # non-auth params
            http2=True,
            base_url=settings.backend_api_url,
            verify=settings.backend_api_verify,
        )

        tokens = httpx.post(
            f"{settings.backend_api_url}/token/",
            json={
                "username": settings.backend_api_username.get_secret_value(),
                "password": settings.backend_api_password.get_secret_value(),
            },
            verify=settings.backend_api_verify,
        ).json()
        self.httpx.token = {
            "refresh_token": tokens["refresh"],
            "access_token": tokens["access"],
        }

    async def get_pickle(self, key: str) -> Any | None:
        if data := await self.raw_db.get(key):
            return pickle.loads(data)

    async def set_pickle(self, key: str, value: Any, **kwargs):
        await self.raw_db.set(key, pickle.dumps(value), **kwargs)

    async def delete_pickle(self, key: str):
        await self.raw_db.delete(key)

    async def save_user(self, user: User):
        await self.set_pickle(f"user:{user.telegram_id}", user)
        await self.db.sadd("users", user.telegram_id)

    async def load_user(self, telegram_id: int, app: Application) -> User:
        from app.engine import UserInterpreter

        if not (user := await self.get_pickle(f"user:{telegram_id}")):
            user = user or User(telegram_id=telegram_id)
        statechart = await self.get_statechart(settings.bot.statechart)
        user.interpreter = UserInterpreter(user, app, statechart)
        user.interpreter.__dict__.update(user.interpreter_state)
        await self.save_user(user)
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

    async def get_statechart(self, statechart_id) -> Statechart:
        redis_key = f"statechart:{statechart_id}"
        if statechart := await self.get_pickle(redis_key):
            return statechart
        response = await self.httpx.get(f"/statecharts/{statechart_id}/")
        statechart = Statechart.parse_obj(response.json()["code"])
        await self.set_pickle(redis_key, statechart, ex=60 * 60)
        return statechart
