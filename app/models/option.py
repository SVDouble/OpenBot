from typing import Callable, Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

__all__ = ["Option"]


class Option(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str
    emoji: str = ""
    label: str = ""
    order: int = 0
    value: Any | None = None

    is_active: Callable[[], bool] | None = None

    def __str__(self):
        prefix = f"{self.prefix} " if self.prefix else ""
        return f"{prefix}{self.name}"

    def __len__(self):
        return len(self.name) + 2

    @property
    def prefix(self):
        if self.is_active and self.is_active():
            return "✅"
        return self.emoji
