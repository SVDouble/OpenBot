from typing import Protocol

__all__ = ["Chat", "Bot", "Application"]


class Chat(Protocol):
    first_name: str
    last_name: str


class Bot(Protocol):
    async def get_chat(self, telegram_id: int) -> Chat:
        ...

    async def send_message(self, *args, **kwargs):
        ...

    async def send_photo(self, *args, **kwargs):
        ...


class Application(Protocol):
    bot: Bot
