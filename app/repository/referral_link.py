from app.models import ReferralLink
from app.repository.model import BaseRoModelRepository
from app.utils import get_settings

__all__ = ["ReferralLinkRepository"]

settings = get_settings()


class ReferralLinkRepository(BaseRoModelRepository[ReferralLink]):
    model = ReferralLink
    key = "ref"
    ex = settings.cache_ex_referral_link
    url = "/referral_links"

    async def _get_retrieve_kwargs(self, alias: str, **kwargs) -> dict:
        return {"params": {"alias": alias} if alias else {"is_default": True}}

    async def get(self, alias: str = "", **kwargs) -> ReferralLink | None:
        return await super().get(alias, **kwargs)
