import asyncio
import datetime

import sismic.model
from sismic.clock import UtcClock
from sismic.interpreter import Interpreter
from sismic.io.datadict import import_from_dict
from telegram.ext import Application

from app.models import StateChart, User
from app.settings import get_settings
from app.utils import get_logger

__all__ = ["BotEngine", "UserEngine"]

logger = get_logger(__file__)
settings = get_settings()


class Engine:
    def __init__(self, statechart: StateChart, context: dict):
        statechart = import_from_dict(dict(statechart=statechart.dict(by_alias=True)))
        statechart.validate()
        self.interpreter: Interpreter = Interpreter(
            statechart, ignore_contract=True, initial_context=context, clock=UtcClock()
        )

    async def dispatch_event(self, event: str) -> list[sismic.model.MacroStep]:
        logger.debug(f"{type(self).__name__} got {event=}")
        self.interpreter.queue(event)
        return self.interpreter.execute(max_steps=42)

    def __getstate__(self):
        return {"interpreter": self.interpreter}


class UserEngine(Engine):
    def __init__(self, user: User, app: Application, statechart: StateChart):
        # TODO: define proper Evaluator
        super().__init__(statechart, {"receive": print})
        self.user = user
        self.app = app


class BotEngine(Engine):
    def __init__(self, app: Application, statechart: StateChart):
        # TODO: define proper Evaluator
        super().__init__(statechart, {"bot": app.bot})
        self.app = app
        self._clock_interval = datetime.timedelta(seconds=1)
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
