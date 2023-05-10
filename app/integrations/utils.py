import contextlib

from httpx import HTTPStatusError

from app.interfaces import Application
from app.profile import Session, get_profile
from app.utils import get_logger, get_repository, get_settings

__all__ = ["get_cache"]

logger = get_logger(__file__)
settings = get_settings()
repo = get_repository()


@contextlib.asynccontextmanager
async def get_cache(telegram_id: int, app: Application):
    cache = await repo.caches.load_for_user(telegram_id, app)
    with Session.begin() as session:
        cache.session = session
        profile = get_profile(session, cache.interpreter.role.label, cache.user.id)
        cache.interpreter.context.update(profile=profile)
        yield cache
        await repo.caches.save(cache)
        state = cache.modify_state(await repo.states.get(cache.id))
        try:
            await repo.states.patch(state)
        except HTTPStatusError:
            await app.bot.send_message(
                telegram_id, "We've reset your account, so you can start anew"
            )
            await repo.users.remove(cache.user)
        else:
            await repo.users.patch(cache.user)
        cache.session = None
