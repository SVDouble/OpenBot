import functools
import pickle
from typing import Any, Callable, Self
from uuid import UUID

import httpx
import redis.asyncio as redis

__all__ = ["Repository"]

from authlib.integrations.httpx_client import AsyncOAuth2Client
from httpx import AsyncClient
from telegram import Chat
from telegram.ext import Application

from app.exceptions import AccessDeniedError, PublicError
from app.models import (
    Account,
    Answer,
    Bot,
    Callback,
    Content,
    ProgramState,
    ReferralLink,
    Statechart,
    User,
    Question,
)
from app.models.role import Role
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


# noinspection PyMethodMayBeStatic
class Repository:
    def __init__(self):
        self.db = init_redis_client()
        self.raw_db = init_redis_client(decode_responses=False)
        self.httpx = self._get_httpx_client()

    def _get_httpx_client(self) -> AsyncClient:
        token = httpx.post(
            f"{settings.backend_api_url}/token/",
            json={
                "username": settings.backend_api_username.get_secret_value(),
                "password": settings.backend_api_password.get_secret_value(),
            },
            verify=settings.backend_api_verify,
        ).json()
        return AsyncOAuth2Client(
            token_endpoint="/token/refresh/",
            token=token,
            # non-auth params
            http2=True,
            base_url=settings.backend_api_url,
            verify=settings.backend_api_verify,
        )

    async def get_pickle(self, key: str) -> Any | None:
        if data := await self.raw_db.get(key):
            return pickle.loads(data)

    async def set_pickle(self, key: str, value: Any, *, ex: int | None, **kwargs):
        await self.raw_db.set(key, pickle.dumps(value), ex=ex, **kwargs)

    async def delete_pickle(self, key: str):
        await self.raw_db.delete(key)

    def get_state_key(self, telegram_id: int, state_id: str | UUID) -> str:
        return f"{telegram_id}:state:{state_id}"

    def get_callback_key(self, state: ProgramState, callback_id: UUID | str) -> str:
        return f"{self.get_state_key(state.user.telegram_id, state.id)}:callback:{callback_id}"

    def get_account_key(self, telegram_id: int) -> str:
        return f"{telegram_id}:account"

    def get_user_key(self, telegram_id: int, *_, **__) -> str:
        return f"{telegram_id}:user"

    def get_referral_link_key(self, alias: str = "") -> str:
        return f"ref:{alias!r}"  # alias might be empty

    def get_bot_key(self, bot_id: UUID) -> str:
        return f"bot:{bot_id}"

    def get_statechart_key(self, statechart_id: UUID) -> str:
        return f"statechart:{statechart_id}"

    def get_content_key(self, content_id: UUID | str) -> str:
        return f"content:{content_id}"

    def get_role_key(self, role_id: UUID | str) -> str:
        return f"role:{role_id}"

    def get_question_key(
        self,
        question_id: UUID | str | None = None,
        label: str | None = None,
    ) -> str:
        if not bool(question_id) ^ bool(label):
            raise RuntimeError("Either question_id or label must be present")
        return f"question:{question_id or label}"

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
        user = await self.get_user(telegram_id, app)

        if state is None:
            if state_id != "latest":
                raise KeyError(f"State {key} does not exist")
            state = ProgramState(user=user)
        else:
            state.user = user

        role = await self.get_role(user.role)
        statechart = await self.get_statechart(role.statechart)
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

    @staticmethod
    def cached(*, key: str | Callable, ex: int):
        def decorator(fetch_obj):
            @functools.wraps(fetch_obj)
            async def wrapper(self: Self, *args, **kwargs):
                redis_key = key if isinstance(key, str) else key(self, *args, **kwargs)

                if (obj := await self.get_pickle(redis_key)) is not None:
                    return obj
                if (obj := await fetch_obj(self, *args, **kwargs)) is not None:
                    await self.set_pickle(redis_key, obj, ex=ex)
                    return obj

            return wrapper

        return decorator

    @cached(key=get_statechart_key, ex=settings.cache_ex_statechart)
    async def get_statechart(self, statechart_id: UUID) -> Statechart:
        response = await self.httpx.get(f"/statecharts/{statechart_id}/")
        return Statechart.parse_obj(response.json()["code"])

    @cached(key=get_account_key, ex=settings.cache_ex_account)
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

    @cached(key=get_referral_link_key, ex=settings.cache_ex_referral_link)
    async def get_referral_link(self, alias: str = "") -> ReferralLink | None:
        params = {"alias": alias} if alias else {"is_default": True}
        params["bot"] = str(settings.bot.id)
        response = await self.httpx.get("/referral_links/", params=params)
        if response.is_success and (data := response.json()):
            return ReferralLink.parse_obj(data[0])

    @cached(key=get_user_key, ex=settings.cache_ex_user)
    async def get_user(self, telegram_id: int, app: Application) -> User:
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
            user_id = data[0]["id"]
            return User.parse_obj((await self.httpx.get(f"/users/{user_id}/")).json())

        # create a new user
        account = await self.get_account(telegram_id)
        link = await self.get_referral_link()
        if link is None:
            raise PublicError("Registration is not available at the moment")
        chat: Chat = await app.bot.get_chat(telegram_id)
        response = await self.httpx.post(
            "/users/",
            json={
                "account": str(account.id),
                "telegram_id": telegram_id,
                "bot": str(link.bot),
                "role": str(link.target_role),
                "referral_link": str(link.id),
                "first_name": chat.first_name,
                "last_name": chat.last_name,
            },
        )
        if response.is_success and (data := response.json()):
            return User.parse_obj(data)

        raise PublicError("Couldn't register the user")

    @cached(key=get_bot_key, ex=settings.cache_ex_bot)
    async def get_bot(self, bot_id: UUID) -> Bot | None:
        response = await self.httpx.get(f"/bots/{bot_id}/")
        if response.is_success and (data := response.json()):
            return Bot.parse_obj(data)
        raise PublicError("Couldn't get the bot info")

    @cached(key=get_content_key, ex=settings.cache_ex_content)
    async def get_content(self, content_id: UUID | str) -> Content | None:
        response = await self.httpx.get(f"/contents/{content_id}/")
        if response.is_success and (data := response.json()):
            return Content.parse_obj(data)

    @cached(key=get_role_key, ex=settings.cache_ex_role)
    async def get_role(self, role_id: UUID | str) -> Role | None:
        response = await self.httpx.get(f"/roles/{role_id}/")
        if response.is_success and (data := response.json()):
            return Role.parse_obj(data)
        raise PublicError("Couldn't fetch the role")

    @cached(key=get_question_key, ex=settings.cache_ex_question)
    async def get_question(
        self,
        question_id: UUID | str | None = None,
        label: str | None = None,
    ) -> Question:
        if question_id:
            response = await self.httpx.get(f"/questions/{question_id}/")
            if response.is_success and (data := response.json()):
                return Question.parse_obj(data)
        elif label:
            response = await self.httpx.get(
                f"/questions/", params={"bot": settings.bot.id, "label": label}
            )
            if response.is_success and (data := response.json()):
                return Question.parse_obj(data[0])
        raise PublicError("Couldn't fetch the question")

    async def save_answer(self, answer: Answer) -> Answer:
        data = answer.json(exclude_none=True)
        headers = {"Content-Type": "application/json"}
        response = await self.httpx.post(f"/answers/", headers=headers, data=data)
        response.raise_for_status()
        if response.is_success and (data := response.json()):
            return Answer.parse_obj(data)
