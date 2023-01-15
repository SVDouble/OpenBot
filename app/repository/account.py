from app.models import Account
from app.repository.model import BaseRwModelRepository
from app.utils import get_settings

__all__ = ["AccountRepository"]

settings = get_settings()


class AccountRepository(BaseRwModelRepository[Account]):
    model = Account
    key = "account"
    ex = settings.cache_ex_account
    url = "/accounts"

    async def _get_retrieve_kwargs(self, id_: int, **kwargs) -> dict:
        return {"params": {"telegram_id": id_}}

    async def _get_create_kwargs(self, id_: int, **kwargs) -> dict:
        return {"json": {"telegram_id": id_}}
