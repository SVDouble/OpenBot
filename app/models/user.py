import datetime
from enum import IntEnum
from uuid import UUID

from pydantic import BaseModel

from app.models.role import Role

__all__ = ["VerificationStatus", "User"]


class VerificationStatus(IntEnum):
    VERIFIED = 5
    PENDING_VERIFICATION = 4
    UNVERIFIED = 3
    CANCELLED = 2
    REJECTED = 1
    SUSPENDED = 0


class User(BaseModel):
    account: UUID
    telegram_id: int
    first_name: str
    last_name: str
    bot: UUID
    role: Role
    referral_link: UUID
    is_staff: bool
    is_active: bool
    is_registered: bool
    is_matchable: bool
    verification_status: VerificationStatus
    date_joined: datetime.datetime
