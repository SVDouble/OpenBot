import asyncio
import datetime
from typing import Mapping, Any, Callable

import sismic.model
from sismic.clock import UtcClock
from sismic.io.datadict import import_from_dict
from telegram.ext import Application

from app.asismic.interpreter import AsyncInterpreter
from app.asismic.python import AsyncPythonEvaluator
from app.models import StateChart, User
from app.utils import get_logger, get_settings

__all__ = ["BaseInterpreter", "UserInterpreter", "BotInterpreter"]

logger = get_logger(__file__)
settings = get_settings()


class BaseEvaluator(AsyncPythonEvaluator):
    @property
    def context(self) -> dict:
        return self._context

    def __getstate__(self):
        state = self.__dict__.copy()
        state["_context"] = {}
        return state

    async def _execute_code(
        self, code: str | None, *, additional_context: Mapping[str, Any] = None
    ) -> list[sismic.model.Event]:
        interpreter: UserInterpreter = self._interpreter

        def set_variable(name: str, value):
            self._context[name] = value

        additional_context = (additional_context or {}) | {
            "bot": interpreter.app.bot,
            "set": set_variable,
            "run": lambda future: asyncio.create_task(future),
        }
        return await super()._execute_code(code, additional_context=additional_context)


class BaseInterpreter(AsyncInterpreter):
    def __init__(
        self,
        statechart: StateChart,
        evaluator_klass: Callable[..., BaseEvaluator] = BaseEvaluator,
    ):
        statechart = import_from_dict(dict(statechart=statechart.dict(by_alias=True)))
        statechart.validate()
        self._evaluator_klass = evaluator_klass
        super().__init__(
            statechart,
            evaluator_klass=evaluator_klass,
            ignore_contract=True,
            clock=UtcClock(),
        )

    async def dispatch_event(
        self, event: str | sismic.model.Event
    ) -> list[sismic.model.MacroStep]:
        logger.debug(f"{type(self).__name__} got {event=}")
        self.queue(event)
        steps = await self.execute(max_steps=42)
        return steps

    @property
    def context(self) -> dict:
        return self._evaluator.context

    def __getstate__(self):
        state = self.__dict__.copy()
        del state["_evaluator"]
        return state

    def __setstate__(self, state):
        self.__dict__ = state
        self._evaluator = self._evaluator_klass(self)
        asyncio.create_task(self._evaluator.execute_statechart(self._statechart))


class UserEvaluator(BaseEvaluator):
    async def _execute_code(
        self, code: str | None, *, additional_context: Mapping[str, Any] = None
    ) -> list[sismic.model.Event]:
        interpreter: UserInterpreter = self._interpreter
        additional_context = (additional_context or {}) | {
            "user": (user := interpreter.user),
            "expect": user.expect,
            "accept": user.accept,
            "debug": logger.debug,
        }
        return await super()._execute_code(code, additional_context=additional_context)


class UserInterpreter(BaseInterpreter):
    def __init__(self, user: User, app: Application, statechart: StateChart):
        super().__init__(statechart, evaluator_klass=UserEvaluator)
        self.user = user
        self.app = app

    def __getstate__(self):
        state = super().__getstate__()
        del state["user"]
        del state["app"]
        return state


class BotEvaluator(BaseEvaluator):
    pass


class BotInterpreter(BaseInterpreter):
    def __init__(self, app: Application, statechart: StateChart):
        super().__init__(statechart, evaluator_klass=BotEvaluator)
        self.app = app
        self._clock_interval = datetime.timedelta(seconds=5)
        self._last_activity_time = datetime.datetime.min
        self._is_active = False

    async def _run_clock(self):
        while self._is_active:
            now = datetime.datetime.now()
            if now - self._last_activity_time > self._clock_interval:
                await self.dispatch_event("clock")
            await asyncio.sleep(self._clock_interval.seconds)

    async def dispatch_event(self, event: str) -> list[sismic.model.MacroStep]:
        steps = await super().dispatch_event(event)
        self._last_activity_time = datetime.datetime.now()
        return steps

    async def run(self):
        logger.info("starting the engine")
        self._is_active = True
        await self._run_clock()

    async def stop(self):
        logger.info(f"stopping the engine'")
        self._is_active = False
