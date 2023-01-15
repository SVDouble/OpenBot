import asyncio
import datetime
from typing import Any, Mapping

import sismic.model
from telegram.ext import Application

from app.engine.core import BaseEvaluator, BaseInterpreter
from app.models import Statechart
from app.utils import get_logger, get_settings

__all__ = ["BotEvaluator", "BotInterpreter"]

logger = get_logger(__file__)
settings = get_settings()


class BotEvaluator(BaseEvaluator):
    async def _get_shared_context(self) -> dict[str, Any]:
        interpreter: BotInterpreter = self._interpreter
        return {"bot": interpreter.app.bot}

    async def _execute_code(
        self, code: str | None, *, additional_context: Mapping[str, Any] = None
    ) -> list[sismic.model.Event]:
        interpreter: BotInterpreter = self._interpreter
        additional_context = (additional_context or {}) | {"bot": interpreter.app.bot}
        return await super()._execute_code(code, additional_context=additional_context)


class BotInterpreter(BaseInterpreter):
    def __init__(self, app: Application, statechart: Statechart):
        super().__init__(statechart, evaluator_klass=BotEvaluator)
        self.app = app
        self._clock_interval = settings.bot.bot_clock_interval
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
