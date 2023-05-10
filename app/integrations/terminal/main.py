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
    async def get_chat(self, chat_id: int) -> Chat:
        return TerminalChat(chat_id, "John", "Doe")

    async def send_message(self, *args, **kwargs):
        print(f"Got message: {args} {kwargs}")

    async def send_photo(self, *args, **kwargs):
        print(f"Got photo: {args} {kwargs}")


class TerminalApplication(Application):
    def __init__(self):
        self.bot = TerminalBot()


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
    logger.info("Bot has started UwU")
    application = TerminalApplication()
    while True:
        update = {"chat": application.bot.get_chat(-1)}
        message = input("Enter a message: ")
        if message == "/exit":
            break
        if message.startswith("/"):
            command, *args = message[1:].split()
            update["type"] = "command"
            update["command"] = command
            update["args"] = args
        else:
            update["type"] = "message"
            update["message"] = message
        await handle_update(update, application)
