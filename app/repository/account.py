from app.models import Account
from app.repository.model import ID, BaseRwModelRepository
from app.utils import get_settings

__all__ = ["AccountRepository"]

settings = get_settings()


class AccountRepository(BaseRwModelRepository[Account]):
    model = Account
    key = "account"
    ex = settings.cache_ex_account
    url = "/accounts"

    async def _get_retrieve_kwargs(self, id_: ID | None, **kwargs) -> dict | None:
        if id_ is None:
            return {"params": {"telegram_id": kwargs["telegram_id"]}}

    async def _get_create_kwargs(self, id_: ID | None, **kwargs) -> dict | None:
        return {"json": {"telegram_id": kwargs["telegram_id"]}}
