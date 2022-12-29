import functools
import pickle
from typing import Any, Callable
from uuid import UUID

import httpx
import redis.asyncio as redis

__all__ = ["Repository"]

from authlib.integrations.httpx_client import AsyncOAuth2Client
from telegram.ext import Application

from app.exceptions import AccessDeniedError, PublicError
from app.models import (
    Account,
    Bot,
    Callback,
    ProgramState,
    ReferralLink,
    Statechart,
    User,
)
from app.utils import get_logger, get_settings

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

    async def set_pickle(self, key: str, value: Any, *, ex: int | None, **kwargs):
        await self.raw_db.set(key, pickle.dumps(value), ex=ex, **kwargs)

    async def delete_pickle(self, key: str):
        await self.raw_db.delete(key)

    @classmethod
    def get_state_key(cls, telegram_id: int, state_id: str | UUID) -> str:
        return f"{telegram_id}:state:{state_id}"

    @classmethod
    def get_callback_key(cls, state: ProgramState, callback_id: UUID | str) -> str:
        return f"{cls.get_state_key(state.user.telegram_id, state.id)}:callback:{callback_id}"

    @classmethod
    def get_account_key(cls, telegram_id: int) -> str:
        return f"{telegram_id}:account"

    @classmethod
    def get_user_key(cls, telegram_id: int) -> str:
        return f"{telegram_id}:user"

    @classmethod
    def get_referral_link_key(cls, alias: str) -> str:
        return f"ref:{alias}"

    @classmethod
    def get_bot_key(cls, bot_id: UUID) -> str:
        return f"bot:{bot_id}"

    @classmethod
    def get_statechart_key(cls, statechart_id: UUID) -> str:
        return f"statechart:{statechart_id}"

    async def save_state(self, state: ProgramState):
        telegram_id = state.user.telegram_id
        await self.set_pickle(self.get_state_key(telegram_id, state.id), state, ex=None)
        await self.set_pickle(self.get_state_key(telegram_id, "latest"), state, ex=None)
        await self.db.sadd("users", state.user.telegram_id)

    async def load_state(
        self, telegram_id: int, app: Application, state_id: UUID | str = "latest"
    ) -> ProgramState:
        from app.engine import UserInterpreter

        key = self.get_state_key(telegram_id, state_id)
        state: ProgramState | None = await self.get_pickle(key)
        user = await self.get_user(telegram_id)

        if state is None:
            if state_id != "latest":
                raise KeyError(f"State {key} does not exist")
            state = ProgramState(user=user)
        else:
            state.user = user

        statechart = await self.get_statechart(settings.bot.statechart)
        state.interpreter = UserInterpreter(state, app, statechart)
        state.interpreter.__dict__.update(state.interpreter_state)
        await self.save_state(state)
        return state

    async def reset_state(self, telegram_id: int):
        # TODO: remove obsolete states?
        await self.db.delete(self.get_state_key(telegram_id, "latest"))

    async def get_user_ids(self) -> set[int]:
        return set(int(uid) for uid in await self.db.smembers("users"))

    async def create_callback(self, state: ProgramState, callback: Callback):
        await self.set_pickle(
            self.get_callback_key(state, callback.id), callback, ex=None
        )

    async def get_callback(
        self, state: ProgramState, callback_id: UUID | str
    ) -> Callback | None:
        return await self.get_pickle(self.get_callback_key(state, callback_id))

    async def remove_callback(self, state: ProgramState, callback_id: UUID | str):
        await self.delete_pickle(self.get_callback_key(state, callback_id))

    def cached(self, *, key: str | Callable, ex: int):
        def decorator(fetch_obj):
            @functools.wraps(fetch_obj)
            async def wrapper(*args, **kwargs):
                redis_key = key if isinstance(key, str) else key(*args, **kwargs)

                if (obj := await self.get_pickle(redis_key)) is not None:
                    return obj
                if (obj := await fetch_obj(*args, **kwargs)) is not None:
                    await self.set_pickle(key, obj, ex=ex)
                    return obj

            return wrapper

        return decorator

    @cached(key=get_statechart_key, ex=settings.cache_ex_statecharts)
    async def get_statechart(self, statechart_id: UUID) -> Statechart:
        response = await self.httpx.get(f"/statecharts/{statechart_id}/")
        return Statechart.parse_obj(response.json()["code"])

    @cached(key=get_account_key, ex=settings.cache_ex_accounts)
    async def get_account(self, telegram_id: int) -> Account:
        response = await self.httpx.get(
            "/accounts/",
            params={"telegram_id": telegram_id},
        )
        if response.is_success and (data := response.json()):
            return Account.parse_obj(data[0])
        response = await self.httpx.post(
            "/accounts/", json={"telegram_id": telegram_id}
        )
        if response.is_success and (data := response.json()):
            account: Account = Account.parse_obj(data)
            if not account.is_active:
                raise AccessDeniedError("Your account seems to be inactive")
            return account

        raise PublicError("Couldn't create an account")

    @cached(key=get_referral_link_key, ex=settings.cache_ex_statecharts)
    async def get_referral_link(self, alias: str = "") -> ReferralLink | None:
        params = {"alias": alias} if alias else {"is_default": True}
        response = await self.httpx.get("/referral_links/", params=params)
        if response.is_success and (data := response.json()):
            return ReferralLink.parse_obj(data)

    @cached(key=get_user_key, ex=settings.cache_ex_users)
    async def get_user(self, telegram_id: int) -> User:
        # retrieve the user
        response = await self.httpx.get(
            f"/users/",
            params={
                "is_active": True,
                "telegram_id": telegram_id,
                "bot__username": settings.bot.username,
            },
        )
        if response.is_success and (data := response.json()):
            return User.parse_obj(data[0])

        # create a new user
        account = await self.get_account(telegram_id)
        link = await self.get_referral_link()
        if link is None:
            raise PublicError("Registration is not available at the moment")
        response = await self.httpx.post(
            "/user/",
            json={
                "account": account.id,
                "telegram_id": telegram_id,
                "referral_link": link,
            },
        )
        if response.is_success and (data := response.json()):
            return User.parse_obj(data)

        PublicError("Couldn't register the user")

    @cached(key=get_bot_key, ex=settings.cache_ex_bots)
    async def get_bot(self, bot_id: UUID) -> Bot | None:
        response = await self.httpx.get(f"/bots/{bot_id}/")
        if response.is_success and (data := response.json()):
            return Bot.parse_obj(data)
