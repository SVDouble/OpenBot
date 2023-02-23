from app.models import Role
from app.repository.model import ID, BaseRoModelRepository
from app.utils import get_settings

__all__ = ["RoleRepository"]

settings = get_settings()


class RoleRepository(BaseRoModelRepository[Role]):
    model = Role
    key = "role"
    ex = settings.cache_ex_role
    url = "/roles"

    async def _get_retrieve_kwargs(
        self, id_: ID | None, *, context: dict = None, **kwargs
    ) -> dict | None:
        if id_ is None:
            return {"params": {"bot": settings.bot_id}}
        return None
