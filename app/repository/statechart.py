from app.models import Statechart
from app.repository.model import BaseRoModelRepository
from app.utils import get_settings

__all__ = ["StatechartRepository"]

settings = get_settings()


class StatechartRepository(BaseRoModelRepository[Statechart]):
    model = Statechart
    key = "statechart"
    ex = settings.cache_ex_statechart
    url = "/statecharts"
