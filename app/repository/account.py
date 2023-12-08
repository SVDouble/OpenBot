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

    async def _get_create_kwargs(
        self, id_: ID | None, *, context: dict = None, **kwargs
    ) -> dict | None:
        data = {"telegram_id": kwargs["telegram_id"]}
        if "first_name" in kwargs:
            data["first_name"] = kwargs["first_name"]
        if "last_name" in kwargs:
            data["last_name"] = kwargs["last_name"]
        return {"json": data}
