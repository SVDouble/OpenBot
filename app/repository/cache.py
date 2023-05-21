from telegram.ext import Application

from app.models import Cache
from app.repository.model import BaseModelRepository


class CacheRepository(BaseModelRepository[Cache]):
    model = Cache
    key = "cache"
    ex = None

    async def load_for_user(self, telegram_id: int, app: Application) -> Cache:
        from app.engine import UserInterpreter

        user = await self.core.users.get_or_create(
            telegram_id=telegram_id, context={"app": app}
        )
        role = await self.core.roles.get(user.role)
        statechart = await self.core.statecharts.get(role.statechart)

        # load the state
        state = None
        if user.state:
            state = await self.core.states.get(user.state)
        if state is None:
            state = await self.core.states.create(
                None, user=user, statechart=statechart
            )
            user.state = state.id
            await self.core.users.patch(user)

        # load the interpreter
        if (cache := await self.load(state.id)) is None:
            data = state.data
            data.setdefault("id", state.id)
            data.setdefault("user", user)
            cache = Cache(**data)

        # cache might be outdated, so we have to update user unconditionally
        # it could've been changed through, for instance, patch mutations
        cache.user = user

        interpreter = UserInterpreter(
            cache=cache, app=app, statechart=statechart, role=role, repo=self.core
        )
        if cache.interpreter_cache:
            interpreter.__dict__.update(cache.interpreter_cache.dict(by_alias=True))
        cache.interpreter = interpreter

        return cache
