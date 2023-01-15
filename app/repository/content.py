from app.models import Content
from app.repository.model import BaseRoModelRepository
from app.utils import get_settings

__all__ = ["ContentRepository"]

settings = get_settings()


class ContentRepository(BaseRoModelRepository[Content]):
    model = Content
    key = "content"
    ex = settings.cache_ex_content
    url = "/contents"
