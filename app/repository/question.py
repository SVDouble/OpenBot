from app.models import Question
from app.repository.model import ID, BaseRoModelRepository
from app.utils import get_settings

__all__ = ["QuestionRepository"]

settings = get_settings()


class QuestionRepository(BaseRoModelRepository[Question]):
    model = Question
    key = "question"
    ex = settings.cache_ex_question
    url = "/questions"

    async def _get_retrieve_kwargs(self, id_: ID | None, **kwargs) -> dict | None:
        if id_ is None:
            return {"params": {"bot": str(settings.bot_id), "label": kwargs["label"]}}
