# Terminal Bot integration
# Add the following to docker-compose.yml to enable this integration:
#
# services:
#   engine:
#     entrypoint: [ "python", "-m", "app.integrations.terminal" ]
#     tty: true
#     stdin_open: true
#
# And then run docker compose up && docker attach easybot_engine


from typing import NamedTuple

from app.integrations.utils import get_cache
from app.interfaces import Application, Bot, Chat
from app.utils import get_logger, get_repository, get_settings

logger = get_logger(__file__)
settings = get_settings()
repo = get_repository()


class TerminalChat(Chat):
    def __init__(self, chat_id, first_name: str, last_name: str):
        self.id = chat_id
        self.first_name = first_name
        self.last_name = last_name


class TerminalBot(Bot):
    def __init__(self):
        self._mq = []

    async def get_chat(self, chat_id: int) -> Chat:
        return TerminalChat(chat_id, "John", "Doe")

    async def send_message(self, *args, **kwargs):
        self._mq.append(("message", args, kwargs))

    async def send_photo(self, *args, **kwargs):
        self._mq.append(("photo", args, kwargs))

    def flush_message_queue(self):
        self._mq.clear()

    def get_messages(self):
        yield from self._mq
        self.flush_message_queue()

    def display_all_messages(self):
        def display_text(telegram_id, text, reply_markup=None, *args, **kwargs):
            msg = f"Got a message: {text}"
            if reply_markup:
                msg += f"\n Options: {reply_markup}"
            logger.info(msg)

        def display_photo(
            telegram_id, photo, caption=None, reply_markup=None, *args, **kwargs
        ):
            msg = f"Got a photo: {photo}"
            if caption:
                msg += f"\n Caption: {caption}"
            if reply_markup:
                msg += f"\n Options: {reply_markup}"
            logger.info(msg)

        for message in self.get_messages():
            match message[0]:
                case "message":
                    display_text(*message[1], **message[2])
                case "photo":
                    display_photo(*message[1], **message[2])
                case _:
                    raise ValueError(f"Unknown message type: {message[0]}")


class TerminalApplication(Application):
    def __init__(self):
        self.bot: TerminalBot = TerminalBot()


async def handle_update(update: dict, app: TerminalApplication):
    async with get_cache(update["chat"].id, app) as cache:
        match update["type"]:
            case "message":
                cache.interpreter.context["message"] = update["message"]
                await cache.interpreter.dispatch_event("received message")
            case "command":
                cache.interpreter.context["command"] = update["command"]
                cache.interpreter.context["args"] = update["args"]
                await cache.interpreter.dispatch_event("received command")
            case _:
                raise ValueError(f"Unknown update type: {update['type']}")


async def main():
    logger.info("Initializing the bot...")
    settings.bot = await repo.bots.get(settings.bot_id)
    logger.info("Using the following settings: ")
    logger.info(settings)
    logger.info("Terminal Bot has started UwU")
    application = TerminalApplication()
    # TODO: replace with an interface (include methods like reply_text, reply_photo, etc.)
    Message = NamedTuple("Message", text=str)
    while True:
        try:
            update = {"chat": await application.bot.get_chat(0)}
            message = input("Enter a message: ")
            if message == "/exit":
                break
            if message.startswith("/"):
                command, *args = message[1:].split()
                update["type"] = "command"
                update["command"] = Message(command)
                update["args"] = args
            else:
                update["type"] = "message"
                update["message"] = Message(message)
            await handle_update(update, application)
        except Exception as e:
            logger.error(e)
        else:
            application.bot.display_all_messages()
        finally:
            application.bot.flush_message_queue()
    logger.info("Terminal Bot has stopped")
