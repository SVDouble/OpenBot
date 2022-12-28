import pickle
from typing import Any
from uuid import UUID

import httpx
import redis.asyncio as redis

__all__ = ["Repository"]

from authlib.integrations.httpx_client import AsyncOAuth2Client
from telegram.ext import Application

from app.models import Callback, Statechart, ProgramState
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

    @classmethod
    def get_state_key(cls, telegram_id: int, state_id: str | UUID) -> str:
        return f"{telegram_id}:state:{state_id}"

    @classmethod
    def get_callback_key(cls, state: ProgramState, callback_id: UUID | str) -> str:
        return f"{cls.get_state_key(state.user.telegram_id, state.id)}:callback:{callback_id}"

    async def save_state(self, state: ProgramState):
        telegram_id = state.user.telegram_id
        await self.set_pickle(self.get_state_key(telegram_id, state.id), state)
        await self.set_pickle(self.get_state_key(telegram_id, "latest"), state)
        await self.db.sadd("users", state.user.telegram_id)

    async def load_state(
        self, telegram_id: int, app: Application, state_id: UUID | str = "latest"
    ) -> ProgramState:
        from app.engine import UserInterpreter

        key = self.get_state_key(telegram_id, state_id)
        if (user := await self.get_pickle(key)) is None:
            if state_id != "latest":
                raise KeyError(f"State {key} does not exist")
            user = user or ProgramState(telegram_id=telegram_id)
        statechart = await self.get_statechart(settings.bot.statechart)
        user.interpreter = UserInterpreter(user, app, statechart)
        user.interpreter.__dict__.update(user.interpreter_state)
        await self.save_state(user)
        return user

    async def reset_state(self, telegram_id: int):
        # TODO: remove obsolete states?
        await self.db.delete(self.get_state_key(telegram_id, "latest"))

    async def get_user_ids(self) -> set[int]:
        return set(int(uid) for uid in await self.db.smembers("users"))

    async def create_callback(self, state: ProgramState, callback: Callback):
        await self.set_pickle(self.get_callback_key(state, callback.id), callback)

    async def get_callback(
        self, state: ProgramState, callback_id: UUID | str
    ) -> Callback | None:
        return await self.get_pickle(self.get_callback_key(state, callback_id))

    async def remove_callback(self, state: ProgramState, callback_id: UUID | str):
        await self.delete_pickle(self.get_callback_key(state, callback_id))

    async def get_statechart(self, statechart_id) -> Statechart:
        redis_key = f"statechart:{statechart_id}"
        if statechart := await self.get_pickle(redis_key):
            return statechart
        response = await self.httpx.get(f"/statecharts/{statechart_id}/")
        statechart = Statechart.parse_obj(response.json()["code"])
        await self.set_pickle(redis_key, statechart, ex=60 * 60)
        return statechart
