from app.models import Answer
from app.repository.model import BaseRwModelRepository
from app.utils import get_settings

__all__ = ["AnswerRepository"]

settings = get_settings()


class AnswerRepository(BaseRwModelRepository[Answer]):
    model = Answer
    key = "answer"
    ex = settings.cache_ex_answers
    url = "/answers"

    async def create(self, answer: Answer, **kwargs) -> Answer:
        data = answer.json(exclude_none=True)
        headers = {"Content-Type": "application/json"}
        response = await self.core.httpx.post(
            f"/answers/", headers=headers, content=data
        )
        response.raise_for_status()
        return Answer.parse_obj(response.json())
