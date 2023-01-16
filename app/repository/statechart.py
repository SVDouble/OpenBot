from typing import Any

from app.models import Statechart
from app.repository.model import ID, BaseRoModelRepository
from app.utils import get_settings

__all__ = ["StatechartRepository"]

settings = get_settings()


class StatechartRepository(BaseRoModelRepository[Statechart]):
    model = Statechart
    key = "statechart"
    ex = settings.cache_ex_statechart
    url = "/statecharts"

    def _extract(self, data: Any, id_: ID | None, **kwargs) -> Any:
        return data["code"]
