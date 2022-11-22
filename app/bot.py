import sismic.model
from telegram import Update
from telegram.ext import ContextTypes

from app.models import User
from app.utils import get_logger, get_settings, get_repository

__all__ = ["handle_message", "handle_command", "commands"]

logger = get_logger(__file__)
settings = get_settings()
repo = get_repository()


# commands


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await repo.remove_user(update.effective_user.id)
    await update.message.reply_text("done")


async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("pong")


async def state(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = await User.load(update.effective_user.id, context.application)
    await update.message.reply_text(f"active states: {user.interpreter.configuration}")


commands = {"reset": reset, "ping": ping, "state": state}


# handlers


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = await User.load(update.effective_user.id, context.application)
    user.interpreter.context.update(
        {"update": update, "context": context, "message": update.effective_message}
    )
    await user.interpreter.dispatch_event(sismic.model.Event("message received"))
    await user.save()


async def handle_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = await User.load(update.effective_user.id, context.application)
    user.interpreter.context.update(
        {
            "update": update,
            "context": context,
            "message": (message := update.effective_message),
            "command": message.text[1 : message.entities[0].length],
            "args": context.args,
        }
    )
    await user.interpreter.dispatch_event(sismic.model.Event("command received"))
    await user.save()
