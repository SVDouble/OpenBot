from app.models import State
from app.repository.model import ID, BaseRwModelRepository
from app.utils import get_settings

__all__ = ["StateRepository"]

settings = get_settings()


class StateRepository(BaseRwModelRepository[State]):
    model = State
    key = "state"
    ex = None
    url = "/states"

    async def create(self, id_: ID, **kwargs) -> State:
        state = State(user=kwargs["user"].id, statechart=kwargs["statechart"].id)
        return await super().create(state, **kwargs)

    # TODO: check why statechart configuration differs for patch (the order of states is not the same)
    # if "data" in keys:
    #     logger.critical(
    #         f"Difference in data['interpreter_cache]['configuration']: "
    #         f"{old_data.get('data')['interpreter_cache']['configuration']} -> {new_data['data']['interpreter_cache']['configuration']}"
    #     )
