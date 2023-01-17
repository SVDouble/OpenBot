import pickle
from typing import Any

import httpx
import redis.asyncio as redis
from authlib.integrations.httpx_client import AsyncOAuth2Client
from httpx import AsyncClient, Response

from app.utils import get_logger, get_settings

__all__ = ["Repository"]

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
        import app.repository as repos

        self.db = init_redis_client()
        self.raw_db = init_redis_client(decode_responses=False)
        self.httpx = self._get_httpx_client()

        self.callbacks = repos.CallbackRepository(self)
        self.states = repos.ProgramStateRepository(self)
        self.statecharts = repos.StatechartRepository(self)
        self.bots = repos.BotRepository(self)
        self.contents = repos.ContentRepository(self)
        self.roles = repos.RoleRepository(self)
        self.questions = repos.QuestionRepository(self)
        self.referral_links = repos.ReferralLinkRepository(self)
        self.users = repos.UserRepository(self)
        self.accounts = repos.AccountRepository(self)
        self.answers = repos.AnswerRepository(self)

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
            event_hooks={"response": [self._log_response]},
        )

    async def _log_response(self, response: Response):
        await response.aread()
        request = response.request
        logger.debug(
            f"{request.method} [{response.status_code}, "
            f"{response.elapsed.total_seconds():.2f}s] {request.url}"
        )

    async def get_pickle(self, key: str) -> Any | None:
        if data := await self.raw_db.get(key):
            return pickle.loads(data)

    async def set_pickle(self, key: str, value: Any, *, ex: int | None, **kwargs):
        await self.raw_db.set(key, pickle.dumps(value), ex=ex, **kwargs)

    async def remove_pickle(self, key: str):
        await self.raw_db.delete(key)

    async def mark_user_as_active(self, telegram_id: int):
        await self.db.sadd("users", telegram_id)

    async def get_active_user_ids(self) -> set[int]:
        return set(int(uid) for uid in await self.db.smembers("users"))
