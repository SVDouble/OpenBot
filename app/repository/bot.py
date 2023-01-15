from app.models import Bot
from app.repository.model import BaseRoModelRepository
from app.utils import get_settings

__all__ = ["BotRepository"]

settings = get_settings()


class BotRepository(BaseRoModelRepository[Bot]):
    model = Bot
    key = "bot"
    ex = settings.cache_ex_bot
    url = "/bots"
