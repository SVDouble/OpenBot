from uuid import UUID

from pydantic import BaseModel

from app.models.statechart import Statechart
from app.models.trait import Trait

__all__ = ["Role"]


class Role(BaseModel):
    id: UUID
    bot: UUID
    name: str
    label: str
    statechart: Statechart
    traits: list[Trait]
    is_verification_required: bool
    daily_view_limit: int | None
