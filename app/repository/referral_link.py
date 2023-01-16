from app.models import ReferralLink
from app.repository.model import ID, BaseRoModelRepository
from app.utils import get_settings

__all__ = ["ReferralLinkRepository"]

settings = get_settings()


class ReferralLinkRepository(BaseRoModelRepository[ReferralLink]):
    model = ReferralLink
    key = "ref"
    ex = settings.cache_ex_referral_link
    url = "/referral_links"

    async def _get_retrieve_kwargs(self, id_: ID, **kwargs) -> dict | None:
        if id_ is None:
            alias = kwargs.get("alias")
            return {"params": {"alias": alias} if alias else {"is_default": True}}
