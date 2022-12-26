import datetime
from uuid import UUID

from pydantic import BaseModel

from app.models.statechart import Statechart

__all__ = ["Bot"]


class Bot(BaseModel):
    class Config:
        frozen = True

    id: UUID
    name: str
    username: str
    token: str
    # statechart: Statechart
    date_created: datetime.datetime

    bot_clock_interval: datetime.timedelta = datetime.timedelta(minutes=1)
    user_clock_interval: datetime.timedelta = datetime.timedelta(minutes=1)
