from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

__all__ = ["Callback"]

repo: Any | None = None


class Callback(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    user_telegram_id: int
    target: str
    data: Any
    auto_answer: bool = True
    is_persistent: bool = False

    async def save(self):
        from app.utils import get_repository

        global repo
        repo = repo or get_repository()
        await repo.create_callback(self, self.user_telegram_id)
