from app.models import Match
from app.repository.model import BaseRwModelRepository
from app.utils import get_settings

__all__ = ["MatchRepository"]

settings = get_settings()


class MatchRepository(BaseRwModelRepository[Match]):
    model = Match
    key = "match"
    ex = settings.cache_ex_match
    url = "/matches"
