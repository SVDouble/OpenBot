from functools import partial
from typing import Any

from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.constants import ParseMode
from telegram.ext import Application

from app.engine.core import BaseEvaluator, BaseInterpreter
from app.models import Cache, Question, Role, Statechart
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
            question = await repo.questions.get(label=label)
            if question is None:
                logger.error(f"Question with label='{label}' does not exist")
                raise RuntimeError(f"Question {label} does not exist")
            return question

        async def get_answer(question_label: str, *, key: str | None = "value"):
            return await logic.get_answer(cache, question_label, key=key)

        return {
            "bot": interpreter.app.bot,
            "cache": (cache := interpreter.cache),
            "context": cache.context,
            "repo": repo,
            "user": cache.user,
            "question": cache.question,
            "answers": cache.answers,
            "debug": logger.debug,
            "expect": partial(logic.expect, cache),
            "release": partial(logic.release, cache),
            "clean_input": partial(logic.clean_input, cache),
            "save_answer": partial(logic.save_answer, cache, repo),
            "get_question": get_question,
            "get_answer": get_answer,
            "make_inline_button": partial(logic.make_inline_button, cache, repo),
            "render_template": partial(logic.render_template, cache, repo),
            "get_question_manager": lambda: QuestionManager(cache, repo),
            "get_chat": partial(logic.get_chat, interpreter.app),
            "get_profile": partial(logic.get_user_profile, cache, repo),
        }


class UserInterpreter(BaseInterpreter):
    def __init__(
        self,
        *,
        cache: Cache,
        app: Application,
        statechart: Statechart,
        role: Role,
        repo: Repository,
    ):
        super().__init__(statechart, evaluator_klass=UserEvaluator)
        self.cache = cache
        self.role = role
        self.app = app
        self.repo = repo
