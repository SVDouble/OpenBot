import datetime
from enum import IntEnum
from uuid import UUID

import telegram
from pydantic import BaseModel

__all__ = ["VerificationStatus", "User"]

from telegram.ext import ContextTypes


class VerificationStatus(IntEnum):
    VERIFIED = 5
    PENDING_VERIFICATION = 4
    UNVERIFIED = 3
    CANCELLED = 2
    REJECTED = 1
    SUSPENDED = 0


class User(BaseModel):
    id: UUID
    account: UUID
    telegram_id: int
    first_name: str
    last_name: str
    bot: UUID
    role: UUID
    referral_link: UUID
    state: UUID | None = None
    is_staff: bool
    is_active: bool
    is_registered: bool
    is_matchable: bool
    verification_status: VerificationStatus
    date_joined: datetime.datetime

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    async def get_profile_photo(
        self, context: ContextTypes.DEFAULT_TYPE
    ) -> tuple[telegram.PhotoSize, ...] | None:
        profile_photos = await context.bot.get_user_profile_photos(
            self.telegram_id, limit=1
        )
        if photos := profile_photos.photos:
            return photos[0]
