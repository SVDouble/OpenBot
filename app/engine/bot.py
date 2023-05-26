import asyncio
import datetime
from typing import Any

import sismic.model
from sismic.exceptions import CodeEvaluationError
from telegram.ext import Application

from app.engine.core import BaseEvaluator, BaseInterpreter
from app.models import Statechart
from app.utils import get_logger, get_repository, get_settings

__all__ = ["BotEvaluator", "BotInterpreter"]

logger = get_logger(__file__)
settings = get_settings()
repo = get_repository()


class BotEvaluator(BaseEvaluator):
    async def _get_shared_context(self) -> dict[str, Any]:
        interpreter: BotInterpreter = self._interpreter
        return {"bot": interpreter.app.bot, "repo": repo}


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
                try:
                    await self.dispatch_event("tick")
                except CodeEvaluationError as e:
                    logger.error(f"error while running the engine: {e}")
            await asyncio.sleep(self._clock_interval.seconds)

    async def dispatch_event(self, event: str) -> list[sismic.model.MacroStep]:
        steps = await super().dispatch_event(event)
        self._last_activity_time = datetime.datetime.now()
        return steps

    async def run(self):
        logger.info(f"starting the engine '{self.statechart.name}'")
        self._is_active = True
        await self.dispatch_event("start")
        await self._run_clock()

    async def stop(self):
        logger.info(f"stopping the engine '{self.statechart.name}'")
        self._is_active = False
