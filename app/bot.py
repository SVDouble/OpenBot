from telegram import Update
from telegram.ext import ContextTypes

from app.models import User, Callback
from app.utils import get_logger, get_settings, get_repository

__all__ = ["handle_message", "handle_command", "handle_callback_query", "commands"]

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
    async with (await User.load(update.effective_user.id, context.application)) as user:
        user.interpreter.context.update(
            {
                "update": update,
                "context": context,
                "message": update.effective_message,
            }
        )
        await user.interpreter.dispatch_event("received message")


async def handle_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async with (await User.load(update.effective_user.id, context.application)) as user:
        user.interpreter.context.update(
            {
                "update": update,
                "context": context,
                "message": (message := update.effective_message),
                "command": message.text[1 : message.entities[0].length],
                "args": context.args,
            }
        )
        await user.interpreter.dispatch_event("received command")


async def handle_callback_query(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    callback = await Callback.load(query.data, update.effective_user.id)
    if callback is None:
        await query.answer(text="This callback has expired")
        return
    if callback.auto_answer:
        await query.answer()
    async with (await User.load(update.effective_user.id, context.application)) as user:
        user.interpreter.context.update(
            {
                "update": update,
                "context": context,
                "query": query,
                "callback": callback,
            }
        )
        await user.interpreter.dispatch_event("received callback query")
