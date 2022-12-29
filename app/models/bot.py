import datetime
from uuid import UUID

from pydantic import BaseModel, SecretStr

__all__ = ["Bot"]


class Bot(BaseModel):
    id: UUID
    name: str
    username: str
    token: SecretStr
    statechart: UUID
    date_created: datetime.datetime

    bot_clock_interval: datetime.timedelta = datetime.timedelta(minutes=1)
    user_clock_interval: datetime.timedelta = datetime.timedelta(minutes=1)

    def __hash__(self):
        return hash(self.id)
