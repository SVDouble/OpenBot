from functools import partial
from typing import Any

from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.constants import ParseMode
from telegram.ext import Application

from app.engine.core import BaseEvaluator, BaseInterpreter
from app.models import ProgramState, Statechart
from app.repository import Repository
from app.utils import get_logger

__all__ = ["UserEvaluator", "UserInterpreter"]

logger = get_logger(__file__)


class UserEvaluator(BaseEvaluator):
    @classmethod
    def _get_imports(cls) -> dict:
        import app.models as models

        return {
            "ParseMode": ParseMode,
            "ReplyKeyboardRemove": ReplyKeyboardRemove,
            "ReplyKeyboardMarkup": ReplyKeyboardMarkup,
            **{key: getattr(models, key) for key in models.__all__},
        }

    async def _get_shared_context(self) -> dict[str, Any]:
        import app.engine.logic as logic
        from app.questions import QuestionManager

        interpreter: UserInterpreter = self._interpreter
        repo: Repository = interpreter.repo

        return {
            "bot": interpreter.app.bot,
            "state": (state := interpreter.program_state),
            "repo": repo,
            "user": state.user,
            "question": state.question,
            "answers": state.answers,
            "debug": logger.debug,
            "expect": partial(logic.expect, state),
            "release": partial(logic.release, state),
            "clean_input": partial(logic.clean_input, state),
            "save_answer": partial(logic.save_answer, state, repo),
            "get_question": repo.questions.get,
            "get_answer": partial(logic.get_answer, state),
            "get_total_choices": partial(logic.get_total_choices, state),
            "make_inline_button": partial(logic.make_inline_button, state, repo),
            "render_template": partial(logic.render_template, state, repo),
            "render_question": partial(logic.render_question, state, repo),
            "get_question_manager": lambda: QuestionManager(state, repo),
        }


class UserInterpreter(BaseInterpreter):
    def __init__(
        self,
        *,
        state: ProgramState,
        app: Application,
        statechart: Statechart,
        repo: Repository,
    ):
        super().__init__(statechart, evaluator_klass=UserEvaluator)
        self.program_state = state
        self.app = app
        self.repo = repo
