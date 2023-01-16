from app.models import Callback
from app.repository.model import BaseModelRepository

__all__ = ["CallbackRepository"]

from app.utils import get_settings

settings = get_settings()


class CallbackRepository(BaseModelRepository):
    model = Callback
    ex = None
    key = "callback"
