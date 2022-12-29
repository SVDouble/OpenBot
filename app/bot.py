from functools import wraps
from typing import Callable, Coroutine

from telegram import Update
from telegram.ext import ContextTypes

from app.models import ProgramState
from app.utils import get_logger, get_repository, get_settings

__all__ = ["handle_message", "handle_command", "handle_callback_query", "commands"]

logger = get_logger(__file__)
settings = get_settings()
repo = get_repository()


# commands


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await repo.reset_state(update.effective_user.id)
    await update.message.reply_text("done")


async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("pong")


async def get_state(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = await ProgramState.load(update.effective_user.id, context.application)
    await update.message.reply_text(f"active states: {user.interpreter.configuration}")


commands = {"reset": reset, "ping": ping, "state": get_state}


# handlers


def modifies_state(
    f: Callable[[Update, ContextTypes.DEFAULT_TYPE, ProgramState], Coroutine]
):
    @wraps(f)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        telegram_id = update.effective_user.id
        app = context.application
        async with (await ProgramState.load(telegram_id, app)) as state:
            state.interpreter.context.update(update=update, context=context)
            await f(update, context, state)

    return wrapper


@modifies_state
async def handle_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    state: ProgramState,
) -> None:
    state.interpreter.context["message"] = update.effective_message
    await state.interpreter.dispatch_event("received message")


@modifies_state
async def handle_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    state: ProgramState,
) -> None:
    message = update.effective_message
    command = message.text[1 : message.entities[0].length]
    args = context.args
    state.interpreter.context.update(message=message, command=command, args=args)
    await state.interpreter.dispatch_event("received command")


@modifies_state
async def handle_callback_query(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    state: ProgramState,
) -> None:
    query = update.callback_query
    if callback := await repo.get_callback(state, query.data):
        if callback.auto_answer:
            await query.answer()
        state.interpreter.context.update(query=query, callback=callback)
        await state.interpreter.dispatch_event("received callback query")
    else:
        await query.answer(text="This callback has expired")
