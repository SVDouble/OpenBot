import asyncio
import json
from typing import Literal, Any

import pydantic
from pydantic import PrivateAttr

from app.integrations.utils import get_cache
from app.interfaces import Application, Bot, Chat, Message
from app.utils import get_logger, get_repository, get_settings

logger = get_logger(__file__)
settings = get_settings()
repo = get_repository()


class RedisMessage(pydantic.BaseModel):
    type: str
    pattern: str | None
    channel: str
    data: str


class MqMessage(Message, pydantic.BaseModel):
    chat_id: int
    from_: Literal["user", "bot"] = pydantic.Field(alias="from")
    type: Literal["message", "command", "photo"]

    text: str | None
    caption: str | None
    photo: str | None
    reply_markup: Any | None

    _bot: "MqBot" = PrivateAttr()
    _chat: "MqChat" = PrivateAttr()

    def __init__(self, *, bot: "MqBot", chat: "MqChat", **data):
        super().__init__(**data)
        self._bot = bot
        self._chat = chat
        if self.type == "message" and self.text and self.text.startswith("/"):
            self.type = "command"

    async def reply_text(self, *args, **kwargs):
        await self._bot.send_message(self._chat.id, *args, **kwargs)


class MqChat(Chat):
    def __init__(self, chat_id, first_name: str, last_name: str):
        self.id = chat_id
        self.first_name = first_name
        self.last_name = last_name


class MqBot(Bot):
    def __init__(self, application: "MqApplication"):
        self._chats = {}
        self._app = application
        self._pubsub = repo.db.pubsub()
        self._is_active = False

    async def get_chat(self, chat_id: int) -> MqChat:
        if (chat := self._chats.get(chat_id)) is None:
            chat = self._chats[chat_id] = MqChat(chat_id, f"John{chat_id}", "Doe")
        return chat

    async def send_message(self, chat_id, text, reply_markup=None, **kwargs):
        assert isinstance(chat_id, int), "chat_id must be an integer"
        message = MqMessage(
            chat_id=chat_id,
            from_="bot",
            type="message",
            text=text,
            reply_markup=reply_markup.to_dict() if reply_markup else None,
            bot=self,
            chat=await self.get_chat(chat_id),
        )
        if kwargs:
            logger.debug(f"got unsupported kwargs: {kwargs}")
        await repo.db.publish(f"chat:{chat_id}", json.dumps(message))

    async def send_photo(
        self, chat_id, photo, caption=None, reply_markup=None, **kwargs
    ):
        assert isinstance(chat_id, int), "chat_id must be an integer"
        message = MqMessage(
            chat_id=chat_id,
            from_="bot",
            type="photo",
            caption=caption,
            reply_markup=reply_markup.to_dict() if reply_markup else None,
            bot=self,
            chat=await self.get_chat(chat_id),
        )
        if kwargs:
            logger.debug(f"got unsupported kwargs: {kwargs}")
        await repo.db.publish(f"chat:{chat_id}", json.dumps(message))

    async def _handle_message(self, raw_message: dict):
        redis_message = RedisMessage(**raw_message)
        chat_id = int(redis_message.channel.removeprefix("chat:"))
        chat = await self.get_chat(chat_id)
        message = json.loads(redis_message.data)
        message = MqMessage(**message, bot=self, chat=chat)

        async with get_cache(chat_id, self._app) as cache:
            cache.interpreter.context["message"] = message
            match message.type:
                case "message":
                    await cache.interpreter.dispatch_event("received message")
                case "command":
                    command, *args = message[1:].split()
                    cache.interpreter.context["command"] = command
                    cache.interpreter.context["args"] = args
                    await cache.interpreter.dispatch_event("received command")
                case _:
                    raise ValueError(f"Unknown message type: {message.type}")

    async def _update_active_chats(self, raw_message: dict):
        message = RedisMessage(**raw_message)
        if message.data.startswith("add:"):
            chat_id = int(message.data.removeprefix("add:"))
            await self._add_chat(await self.get_chat(chat_id))
        elif message.data.startswith("remove:"):
            chat_id = int(message.data.removeprefix("remove:"))
            await self._remove_chat(await self.get_chat(chat_id))
        elif message.data == "stop":
            self._is_active = False

    async def _add_chat(self, chat: MqChat):
        self._chats[chat.id] = chat
        await self._pubsub.subscribe(f"chat:{chat.id}", self._handle_message)

    async def _remove_chat(self, chat: MqChat):
        del self._chats[chat.id]
        await self._pubsub.unsubscribe(f"chat:{chat.id}")

    async def run(self):
        await self._pubsub.subscribe("chat", self._update_active_chats)
        self._is_active = True
        while self._is_active:
            await asyncio.sleep(0)
            await self._pubsub.get_message(ignore_subscribe_messages=True, timeout=1)
        await self._pubsub.unsubscribe()
        await self._pubsub.close()


class MqApplication(Application):
    def __init__(self):
        self.bot: MqBot = MqBot(self)


async def main():
    logger.info("Initializing the message queue...")
    settings.bot = await repo.bots.get(settings.bot_id)
    logger.info("Using the following settings: ")
    logger.info(settings)
    logger.info("Message queue has started UwU")
    application = MqApplication()
    await application.bot.run()
    logger.info("Message queue has stopped")
