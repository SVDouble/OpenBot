from telegram import Chat

from app.exceptions import PublicError
from app.models import User
from app.repository.model import ID, BaseRwModelRepository
from app.utils import get_settings

__all__ = ["UserRepository"]

settings = get_settings()


class UserRepository(BaseRwModelRepository[User]):
    model = User
    key = "user"
    ex = settings.cache_ex_user
    url = "/users"
    use_deep_retrieval = True

    async def _get_retrieve_kwargs(self, id_: ID | None, **kwargs) -> dict | None:
        if id_ is None:
            return {
                "params": {
                    "is_active": True,
                    "telegram_id": kwargs["telegram_id"],
                    "bot__username": settings.bot.username,
                }
            }

    async def _get_create_kwargs(self, id_: ID | None, **kwargs) -> dict | None:
        if isinstance(id_, User):
            return await super()._get_create_kwargs(id_, **kwargs)
        telegram_id, app = kwargs["telegram_id"], kwargs["app"]
        account = await self.core.accounts.get(telegram_id)
        link = await self.core.referral_links.get()
        if link is None:
            raise PublicError("Registration is not available at the moment")
        chat: Chat = await app.bot.get_chat(telegram_id)
        return {
            "json": {
                "account": str(account.id),
                "telegram_id": telegram_id,
                "bot": str(link.bot),
                "role": str(link.target_role),
                "referral_link": str(link.id),
                "first_name": chat.first_name,
                "last_name": chat.last_name,
            }
        }