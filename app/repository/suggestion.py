from uuid import UUID

from app.models import Suggestion
from app.repository.model import ID, BaseRwModelRepository
from app.utils import get_settings

__all__ = ["SuggestionRepository"]

settings = get_settings()


class SuggestionRepository(BaseRwModelRepository[Suggestion]):
    model = Suggestion
    key = "suggestions"
    ex = settings.cache_ex_suggestions
    url = "/suggestions"

    async def _get_retrieve_kwargs(self, id_: ID | None, **kwargs) -> dict | None:
        if id_ is None:
            return {"params": {"owner": kwargs["user_id"]}}

    async def pop(self, user_id: UUID) -> Suggestion | None:
        suggestions: list[Suggestion] | None = await self.get(
            user_id=user_id, many=True
        )
        if suggestions:
            suggestion = suggestions.pop()
            if suggestions:
                await self.save(suggestions, user_id=user_id)
            else:
                await self.remove([], user_id=user_id)
            return suggestion
