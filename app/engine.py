import asyncio
import datetime
from typing import Any, Callable, Mapping

import sismic.model
from sismic.clock import UtcClock
from sismic.io.datadict import import_from_dict
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.constants import ParseMode
from telegram.ext import Application

from app.asismic.interpreter import AsyncInterpreter
from app.asismic.python import AsyncPythonEvaluator
from app.models import ProgramState, Statechart
from app.utils import get_logger, get_settings

__all__ = ["BaseInterpreter", "UserInterpreter", "BotInterpreter"]

logger = get_logger(__file__)
settings = get_settings()


class BaseEvaluator(AsyncPythonEvaluator):
    @classmethod
    def _get_imports(cls) -> dict:
        return {}

    @property
    def context(self) -> dict:
        return self._context

    async def _get_shared_context(self) -> dict[str, Any]:
        return {}

    async def _execute_code(
        self, code: str | None, *, additional_context: Mapping[str, Any] = None
    ) -> list[sismic.model.Event]:
        def set_variable(name: str, value):
            self._context[name] = value

        additional_context = (additional_context or {}) | {
            "set": set_variable,
            "run": lambda future: asyncio.create_task(future),
            "logger": get_logger(type(self).__name__),
            **self._get_imports(),
            **(await self._get_shared_context()),
        }
        return await super()._execute_code(code, additional_context=additional_context)

    async def _evaluate_code(
        self, code: str | None, *, additional_context: Mapping[str, Any] = None
    ) -> bool:
        additional_context = (additional_context or {}) | {
            **self._get_imports(),
            **(await self._get_shared_context()),
        }
        return await super()._evaluate_code(code, additional_context=additional_context)


class BaseInterpreter(AsyncInterpreter):
    def __init__(
        self,
        statechart: Statechart,
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
        self.attach(self._event_callback)
        self._is_initialized = False

    async def dispatch_event(
        self, event: str | sismic.model.Event
    ) -> list[sismic.model.MacroStep]:
        if not self._is_initialized:
            await self._evaluator.execute_statechart(self._statechart)
            self._is_initialized = True
        self.queue(event)
        steps = await self.execute(max_steps=42)
        return steps

    async def _event_callback(self, event: sismic.model.MetaEvent):
        if event.name == "event consumed":
            logger.debug(f"{type(self).__name__} got {event.data['event']}")

    @property
    def context(self) -> dict:
        return self._evaluator.context

    @property
    def state(self) -> dict:
        keys = {
            "_ignore_contract",
            "_initialized",
            "_time",
            "_memory",
            "_configuration",
            "_entry_time",
            "_idle_time",
            "_sent_events",
            "_internal_queue",
            "_external_queue",
        }
        return {k: v for k, v in self.__dict__.items() if k in keys}


class UserEvaluator(BaseEvaluator):
    @classmethod
    def _get_imports(cls) -> dict:
        import app.models as models
        from app.questions import QuestionManager

        return {
            "QuestionManager": QuestionManager,
            "ParseMode": ParseMode,
            "ReplyKeyboardRemove": ReplyKeyboardRemove,
            "ReplyKeyboardMarkup": ReplyKeyboardMarkup,
            **{key: getattr(models, key) for key in models.__all__},
        }

    async def _get_shared_context(self) -> dict[str, Any]:
        interpreter: UserInterpreter = self._interpreter
        return {
            "bot": interpreter.app.bot,
            "state": (state := interpreter.program_state),
            "user": state.user,
            "question": state.question,
            "answers": state.answers,
            "debug": logger.debug,
            "expect": state.expect,
            "release": state.release,
            "clean_input": state.clean_input,
            "save_answer": state.save_answer,
        }


class UserInterpreter(BaseInterpreter):
    def __init__(self, state: ProgramState, app: Application, statechart: Statechart):
        super().__init__(statechart, evaluator_klass=UserEvaluator)
        self.program_state = state
        self.app = app


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
