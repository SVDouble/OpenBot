import ast
from types import CodeType
from typing import Any, Dict, List, Optional, Mapping, Iterator

from sismic.code.python import FrozenContext
from sismic.exceptions import CodeEvaluationError
from sismic.model import Event, InternalEvent, MetaEvent, Transition

from .evaluator import AsyncEvaluator

__all__ = ["AsyncPythonEvaluator"]


async def async_exec(code, exposed_context: dict, context: dict):
    wrapper_name = "__async_exec_f"
    wrapper = f"async def {wrapper_name}():\n"
    if context:
        wrapper += "\n".join(f"    global {v}" for v in context)
    else:
        wrapper += "    pass"

    parsed_code = ast.parse(code)
    parsed_wrapper = ast.parse(wrapper)
    for node in parsed_code.body:
        ast.increment_lineno(node)
    parsed_wrapper.body[0].body += parsed_code.body

    context.update(exposed_context)
    exec(compile(parsed_wrapper, filename="<ast>", mode="exec"), context)
    result = await eval(f"{wrapper_name}()", context)
    bad_keys = [
        key for key in context.keys() if key.startswith("__") or key in exposed_context
    ]
    for key in bad_keys:
        del context[key]
    return result


class AsyncPythonEvaluator(AsyncEvaluator):
    """
    A code evaluator that understands Python.

    This evaluator exposes some additional functions/variables:

    - On both code execution and code evaluation:
        - A *time: float* value that represents the current time exposed by interpreter clock.
        - An *active(name: str) -> bool* Boolean function that takes a state name and return *True*
          if and only if this state is currently active, ie. it is in the active configuration of
          the ``Interpreter`` instance that makes use of this evaluator.
    - On code execution:
        - A *send(name: str, **kwargs) -> None* function that takes an event name and additional
          keyword parameters and raises an internal event with it. Raised events are propagated to
          bound statecharts as external events and to the current statechart as internal event.
          If delay is provided, a delayed event is created.
        - A *notify(name: str, **kwargs) -> None* function that takes an event name and additional
          keyword parameters and raises a meta-event with it. Meta-events are only sent to bound
          property statecharts.
        - If the code is related to a transition, the *event: Event* that fires the transition
          is exposed.
        - A *setdefault(name:str, value: Any) -> Any* function that defines and returns variable
          *name* in the global scope if it is not yet defined.
    - On guard or contract evaluation:
        - If the code is related to a transition, an *event: Optional[Event]* variable is exposed.
          This variable contains the currently considered event, or None.
    - On guard or contract (except preconditions) evaluation:
        - An *after(sec: float) -> bool* Boolean function that returns *True* if and only if the
          source state was entered more than *sec* seconds ago. The time is evaluated according to
          Interpreter's clock.
        - A *idle(sec: float) -> bool* Boolean function that returns *True* if and only if the
          source state did not fire a transition for more than *sec* ago. The time is evaluated
          according to Interpreter's clock.
    - On contract (except preconditions) evaluation:
        - A variable *__old__* that has an attribute *x* for every *x* in the context when either
          the state was entered (if the condition involves a state) or the transition was processed
          (if the condition involves a transition). The value of *__old__.x* is a shallow copy
          of *x* at that time.
    - On contract evaluation:
        - A *sent(name: str) -> bool* function that takes an event name and return True if an
          event with the same name was sent during the current step.
        - A *received(name: str) -> bool* function  that takes an event name and return True if
          an event with the same name is currently processed in this step.

    If an exception occurred while executing or evaluating a piece of code, it is propagated by the
    evaluator.

    :param interpreter: the interpreter that will use this evaluator,
        is expected to be an *Interpreter* instance
    :param initial_context: a dictionary that will be used as *__locals__*
    """

    def __init__(
        self, interpreter=None, *, initial_context: Mapping[str, Any] = None
    ) -> None:
        super().__init__(interpreter, initial_context=initial_context)

        self._context = {}  # type: Dict[str, Any]
        self._context.update(initial_context if initial_context else {})
        self._interpreter = interpreter

        # Precompiled code
        self._evaluable_code = {}  # type: Dict[str, CodeType]
        self._executable_code = {}  # type: Dict[str, CodeType]

        # Frozen context for __old__
        self._memory = {}  # type: Dict[int, FrozenContext]

    @property
    def context(self) -> Mapping:
        return self._context

    async def _evaluate_code(
        self, code: Optional[str], *, additional_context: Mapping[str, Any] = None
    ) -> bool:
        """
        Evaluate given code using Python.

        :param code: code to evaluate
        :param additional_context: an optional additional context
        :return: truth value of *code*
        """
        if code is None:
            return True

        compiled_code = self._evaluable_code.get(code, None)
        if compiled_code is None:
            compiled_code = self._evaluable_code.setdefault(
                code, compile(code, "<string>", "eval")
            )

        exposed_context = {
            "active": lambda s: s in self._interpreter.configuration,
            "time": self._interpreter.time,
        }
        exposed_context.update(
            additional_context if additional_context is not None else {}
        )

        try:
            return bool(eval(compiled_code, exposed_context, self._context))
        except Exception as e:
            raise CodeEvaluationError(
                '"{}" occurred while evaluating "{}"'.format(e, code)
            ) from e

    async def _execute_code(
        self, code: Optional[str], *, additional_context: Mapping[str, Any] = None
    ) -> List[Event]:
        """
        Execute given code using Python.

        :param code: code to execute
        :param additional_context: an optional additional context
        :return: a list of sent events
        """
        if code is None:
            return []

        sent_events = []  # type: List[Event]

        exposed_context = {
            "active": lambda name: name in self._interpreter.configuration,
            "time": self._interpreter.time,
            "send": lambda name, **kwargs: sent_events.append(
                InternalEvent(name, **kwargs)
            ),
            "notify": lambda name, **kwargs: sent_events.append(
                MetaEvent(name, **kwargs)
            ),
        }
        exposed_context.update(
            additional_context if additional_context is not None else {}
        )

        try:
            await async_exec(code, exposed_context, self._context)
            return sent_events
        except Exception as e:
            raise CodeEvaluationError(
                '"{}" occurred while executing "{}"'.format(e, code)
            ) from e

    async def evaluate_guard(
        self, transition: Transition, event: Optional[Event] = None
    ) -> bool:
        """
        Evaluate the guard for given transition.

        :param transition: the considered transition
        :param event: instance of *Event* if any
        :return: truth value of *code*
        """
        additional_context = {
            "after": (
                lambda seconds: self._interpreter.time - seconds
                >= self._interpreter._entry_time[transition.source]
            ),
            "idle": (
                lambda seconds: self._interpreter.time - seconds
                >= self._interpreter._idle_time[transition.source]
            ),
            "event": event,
        }
        return await self._evaluate_code(
            getattr(transition, "guard", None), additional_context=additional_context
        )

    async def evaluate_preconditions(
        self, obj, event: Optional[Event] = None
    ) -> Iterator[str]:
        """
        Evaluate the preconditions for given object (either a *StateMixin* or a
        *Transition*) and return a list of conditions that are not satisfied.

        :param obj: the considered state or transition
        :param event: an optional *Event* instance, if any
        :return: list of unsatisfied conditions
        """
        additional_context = {
            "received": lambda name: name == getattr(event, "name", None),
            "sent": lambda name: name
            in [e.name for e in self._interpreter._sent_events],
            "event": event,
        }

        # Deal with __old__ in contracts, only required if there is an invariant or a postcondition
        if (
            len(getattr(obj, "invariants", [])) > 0
            or len(getattr(obj, "postconditions", [])) > 0
        ):
            self._memory[id(obj)] = FrozenContext(self._context)

        return [
            c
            for c in getattr(obj, "preconditions", [])
            if not await self._evaluate_code(c, additional_context=additional_context)
        ]

    async def evaluate_invariants(
        self, obj, event: Optional[Event] = None
    ) -> Iterator[str]:
        """
        Evaluate the invariants for given object (either a *StateMixin* or a
        *Transition*) and return a list of conditions that are not satisfied.

        :param obj: the considered state or transition
        :param event: an optional *Event* instance, if any
        :return: list of unsatisfied conditions
        """
        state_name = obj.source if isinstance(obj, Transition) else obj.name

        additional_context = {
            "__old__": self._memory.get(id(obj), None),
            "after": (
                lambda seconds: self._interpreter.time - seconds
                >= self._interpreter._entry_time[state_name]
            ),
            "idle": (
                lambda seconds: self._interpreter.time - seconds
                >= self._interpreter._idle_time[state_name]
            ),
            "received": lambda name: name == getattr(event, "name", None),
            "sent": lambda name: name
            in [e.name for e in self._interpreter._sent_events],
            "event": event,
        }

        return [
            c
            for c in getattr(obj, "invariants", [])
            if not await self._evaluate_code(c, additional_context=additional_context)
        ]

    async def evaluate_postconditions(
        self, obj, event: Optional[Event] = None
    ) -> Iterator[str]:
        """
        Evaluate the postconditions for given object (either a *StateMixin* or a
        *Transition*) and return a list of conditions that are not satisfied.

        :param obj: the considered state or transition
        :param event: an optional *Event* instance, if any
        :return: list of unsatisfied conditions
        """
        state_name = obj.source if isinstance(obj, Transition) else obj.name

        additional_context = {
            "__old__": self._memory.get(id(obj), None),
            "after": (
                lambda seconds: self._interpreter.time - seconds
                >= self._interpreter._entry_time[state_name]
            ),
            "idle": (
                lambda seconds: self._interpreter.time - seconds
                >= self._interpreter._idle_time[state_name]
            ),
            "received": lambda name: name == getattr(event, "name", None),
            "sent": lambda name: name
            in [e.name for e in self._interpreter._sent_events],
            "event": event,
        }
        return [
            c
            for c in getattr(obj, "postconditions", [])
            if not await self._evaluate_code(c, additional_context=additional_context)
        ]

    def __getstate__(self):
        attributes = self.__dict__.copy()
        attributes["_executable_code"] = dict()  # Code fragment cannot be pickled
        attributes["_evaluable_code"] = dict()  # Code fragment cannot be pickled
        return attributes
