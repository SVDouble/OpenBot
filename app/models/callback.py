from typing import Any, Self
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

__all__ = ["Callback"]

repo: Any | None = None


class Callback(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    user_telegram_id: int
    data: Any
    auto_answer: bool = True
    is_persistent: bool = False

    async def save(self):
        from app.utils import get_repository

        global repo
        repo = repo or get_repository()
        await repo.create_callback(self, self.user_telegram_id)

    @classmethod
    async def load(cls, callback_id: str, user_telegram_id: int) -> Self | None:
        from app.utils import get_repository

        global repo
        repo = repo or get_repository()
        return await repo.get_callback(callback_id, user_telegram_id)
