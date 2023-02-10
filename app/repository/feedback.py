from app.models import Feedback
from app.repository.model import BaseRwModelRepository
from app.utils import get_settings

__all__ = ["FeedbackRepository"]

settings = get_settings()


class FeedbackRepository(BaseRwModelRepository[Feedback]):
    model = Feedback
    key = "feedback"
    ex = settings.cache_ex_feedbacks
    url = "/feedbacks"
