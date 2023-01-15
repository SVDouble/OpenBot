import asyncio
from typing import Any, Callable, Mapping

import sismic.model
from sismic.clock import UtcClock
from sismic.io.datadict import import_from_dict

from app.asismic.interpreter import AsyncInterpreter
from app.asismic.python import AsyncPythonEvaluator
from app.models import Statechart
from app.utils import get_logger, get_settings

__all__ = ["BaseInterpreter", "BaseEvaluator"]

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
