import abc
from typing import Any, Iterable, List, Mapping, Optional

from sismic.exceptions import CodeEvaluationError
from sismic.model import Event, Statechart, StateMixin, Transition

__all__ = ["AsyncEvaluator"]


class AsyncEvaluator(metaclass=abc.ABCMeta):
    """
    Abstract base class for any evaluator.

    An instance of this class defines what can be done with piece of codes
    contained in a statechart (condition, action, etc.).

    Notice that the execute_* methods are called at each step, even if there is no
    code to execute. This allows the evaluator to keep track of the states that are
    entered or exited, and of the transitions that are processed.

    :param interpreter: the interpreter that will use this evaluator,
        is expected to be an *Interpreter* instance
    :param initial_context: an optional dictionary to populate the context
    """

    @abc.abstractmethod
    def __init__(
        self, interpreter=None, *, initial_context: Mapping[str, Any] = None
    ) -> None:
        pass

    @property
    @abc.abstractmethod
    def context(self) -> Mapping[str, Any]:
        """
        The context of this evaluator. A context is a dict-like mapping between
        variables and values that is expected to be exposed when the code is evaluated.
        """
        raise NotImplementedError()

    @abc.abstractmethod
    async def _evaluate_code(
        self, code: str, *, additional_context: Mapping[str, Any] = None
    ) -> bool:
        """
        Generic method to evaluate a piece of code. This method is a fallback if one of
        the other evaluate_* methods is not overridden.

        :param code: code to evaluate
        :param additional_context: an optional additional context
        :return: truth value of *code*
        """
        raise NotImplementedError()

    @abc.abstractmethod
    async def _execute_code(
        self, code: str, *, additional_context: Mapping[str, Any] = None
    ) -> List[Event]:
        """
        Generic method to execute a piece of code. This method is a fallback if one
        of the other execute_* methods is not overridden.

        :param code: code to execute
        :param additional_context: an optional additional context
        :return: a list of sent events
        """
        raise NotImplementedError()

    async def execute_statechart(self, statechart: Statechart):
        """
        Execute the initial code of a statechart.
        This method is called at the very beginning of the execution.

        :param statechart: statechart to consider
        """
        if statechart.preamble:
            events = await self._execute_code(statechart.preamble)
            if len(events) > 0:
                raise CodeEvaluationError(
                    "Events cannot be raised by statechart preamble"
                )

    async def evaluate_guard(
        self, transition: Transition, event: Optional[Event] = None
    ) -> Optional[bool]:
        """
        Evaluate the guard for given transition.

        :param transition: the considered transition
        :param event: instance of *Event* if any
        :return: truth value of *code*
        """
        if transition.guard:
            return await self._evaluate_code(
                transition.guard, additional_context={"event": event}
            )
        return None

    async def execute_action(
        self, transition: Transition, event: Optional[Event] = None
    ) -> List[Event]:
        """
        Execute the action for given transition.
        This method is called for every transition that is processed, even those with no *action*.

        :param transition: the considered transition
        :param event: instance of *Event* if any
        :return: a list of sent events
        """
        if transition.action:
            return await self._execute_code(
                transition.action, additional_context={"event": event}
            )
        else:
            return []

    async def execute_on_entry(self, state: StateMixin) -> List[Event]:
        """
        Execute the on entry action for given state.
        This method is called for every state that is entered, even those with no *on_entry*.

        :param state: the considered state
        :return: a list of sent events
        """
        code = getattr(state, "on_entry", None)
        if code:
            return await self._execute_code(code)
        else:
            return []

    async def execute_on_exit(self, state: StateMixin) -> List[Event]:
        """
        Execute the on exit action for given state.
        This method is called for every state that is exited, even those with no *on_exit*.

        :param state: the considered state
        :return: a list of sent events
        """
        code = getattr(state, "on_exit", None)
        if code:
            return await self._execute_code(code)
        else:
            return []

    async def evaluate_preconditions(
        self, obj, event: Optional[Event] = None
    ) -> Iterable[str]:
        """
        Evaluate the preconditions for given object (either a *StateMixin* or a
        *Transition*) and return a list of conditions that are not satisfied.

        :param obj: the considered state or transition
        :param event: an optional *Event* instance, if any
        :return: list of unsatisfied conditions
        """
        event_d = {"event": event} if isinstance(obj, Transition) else None
        return [
            c
            for c in getattr(obj, "preconditions", [])
            if not await self._evaluate_code(c, additional_context=event_d)
        ]

    async def evaluate_invariants(
        self, obj, event: Optional[Event] = None
    ) -> Iterable[str]:
        """
        Evaluate the invariants for given object (either a *StateMixin* or a
        *Transition*) and return a list of conditions that are not satisfied.

        :param obj: the considered state or transition
        :param event: an optional *Event* instance, if any
        :return: list of unsatisfied conditions
        """
        event_d = {"event": event} if isinstance(obj, Transition) else None
        return [
            c
            for c in getattr(obj, "invariants", [])
            if not await self._evaluate_code(c, additional_context=event_d)
        ]

    async def evaluate_postconditions(
        self, obj, event: Optional[Event] = None
    ) -> Iterable[str]:
        """
        Evaluate the postconditions for given object (either a *StateMixin* or a
        *Transition*) and return a list of conditions that are not satisfied.

        :param obj: the considered state or transition
        :param event: an optional *Event* instance, if any
        :return: list of unsatisfied conditions
        """
        event_d = {"event": event} if isinstance(obj, Transition) else None
        return [
            c
            for c in getattr(obj, "postconditions", [])
            if not await self._evaluate_code(c, additional_context=event_d)
        ]
