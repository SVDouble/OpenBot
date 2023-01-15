from app.models.role import Role
from app.repository.model import BaseRoModelRepository
from app.utils import get_settings

__all__ = ["RoleRepository"]

settings = get_settings()


class RoleRepository(BaseRoModelRepository[Role]):
    model = Role
    key = "role"
    ex = settings.cache_ex_role
    url = "/roles"
