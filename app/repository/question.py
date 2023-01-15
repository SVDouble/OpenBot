from uuid import UUID

from app.models import Question
from app.repository.model import BaseRoModelRepository
from app.utils import get_settings

__all__ = ["QuestionRepository"]

settings = get_settings()


class QuestionRepository(BaseRoModelRepository[Question]):
    model = Question
    key = "question"
    ex = settings.cache_ex_question
    url = "/questions"

    def _make_key(self, id_: int | str | UUID | Question, **kwargs) -> str:
        return super()._make_key(id_ or kwargs["label"], **kwargs)

    def _make_url(self, id_: int | str | UUID | Question, **kwargs):
        return super()._make_url(id_, **kwargs) if id_ else f"{self.url}/"
