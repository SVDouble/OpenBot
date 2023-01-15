from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

__all__ = ["Callback"]


class Callback(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    state_id: UUID
    data: Any
    auto_answer: bool = True
    is_persistent: bool = False
