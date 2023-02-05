from functools import partial
from typing import Any

from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.constants import ParseMode
from telegram.ext import Application

from app.engine.core import BaseEvaluator, BaseInterpreter
from app.models import ProgramState, Question, Role, Statechart, Suggestion
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

        async def get_question(label: str) -> Question:
            return await repo.questions.get(label=label)

        async def get_next_suggestion() -> Suggestion | None:
            return await repo.suggestions.pop(user_id=state.user.id)

        async def get_answer(question_label: str, *, key: str | None = "value"):
            return await logic.get_answer(state, question_label, key=key)

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
            "get_question": get_question,
            "get_answer": get_answer,
            "get_next_suggestion": get_next_suggestion,
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
        role: Role,
        repo: Repository,
    ):
        super().__init__(statechart, evaluator_klass=UserEvaluator)
        self.program_state = state
        self.role = role
        self.app = app
        self.repo = repo
