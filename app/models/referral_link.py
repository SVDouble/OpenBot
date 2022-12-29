from typing import Any
from uuid import UUID

from pydantic import BaseModel

__all__ = ["ReferralLink"]


class ReferralLink(BaseModel):
    id: UUID
    bot: UUID
    owner: UUID
    name: str
    alias: str
    is_active: bool
    user_limit: int

    target_role: UUID
    target_answers: Any
