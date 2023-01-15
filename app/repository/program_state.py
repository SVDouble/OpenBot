from uuid import UUID

from telegram.ext import Application

from app.models import ProgramState
from app.repository.model import BaseRwModelRepository
from app.utils import get_settings

__all__ = ["ProgramStateRepository"]

settings = get_settings()


class ProgramStateRepository(BaseRwModelRepository[ProgramState]):
    model = ProgramState
    key = "state"
    ex = None
    url = "/states"

    async def create(
        self, id_: int | str | UUID | ProgramState, **kwargs
    ) -> ProgramState:
        return ProgramState(user=kwargs["user"])

    async def load_for_user(self, telegram_id: int, app: Application) -> ProgramState:
        from app.engine import UserInterpreter

        user = await self.core.users.get(telegram_id, app=app)
        state = await self.get_or_create(user.state_id, user=user)

        # load the interpreter
        role = await self.core.roles.get(user.role)
        statechart = await self.core.statecharts.get(role.statechart)
        state.interpreter = UserInterpreter(
            state=state, app=app, statechart=statechart, repo=self.core
        )
        state.interpreter.__dict__.update(state.interpreter_state)

        return state
