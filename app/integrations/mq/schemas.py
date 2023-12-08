import pydantic

__all__ = ["RedisMessage"]


class RedisMessage(pydantic.BaseModel):
    type: str
    pattern: str | None
    channel: str
    data: str
