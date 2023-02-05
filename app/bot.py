import html
import json
from functools import wraps
from typing import Callable, Coroutine

from pydantic.json import pydantic_encoder
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from app.models import ProgramState
from app.profile import Session, get_profile
from app.utils import get_logger, get_repository, get_settings

__all__ = [
    "handle_message",
    "handle_command",
    "handle_callback_query",
    "handle_document",
    "handle_photo",
    "commands",
]

logger = get_logger(__file__)
settings = get_settings()
repo = get_repository()


# commands


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    state = await repo.states.load_for_user(
        update.effective_user.id, context.application
    )
    await repo.states.remove(state)
    await update.message.reply_text("done")


async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("pong")


async def get_active_states(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    state = await repo.states.load_for_user(
        update.effective_user.id, context.application
    )
    await update.message.reply_text(f"active states: {state.interpreter.configuration}")


async def dump_state(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        arg = context.args.pop()
    except IndexError:
        await update.message.reply_text("Please specify an attribute to show")
        return
    state = await repo.states.load_for_user(
        update.effective_user.id, context.application
    )
    data = json.dumps(
        state.dict(exclude_none=True).get(arg, None),
        default=pydantic_encoder,
        ensure_ascii=False,
        indent=4,
    )
    await update.message.reply_text(
        f"<code>{html.escape(data)}</code>",
        parse_mode=ParseMode.HTML,
    )


commands = {
    "reset": reset,
    "ping": ping,
    "state": get_active_states,
    "dump": dump_state,
}


# handlers


def modifies_state(
    f: Callable[[Update, ContextTypes.DEFAULT_TYPE, ProgramState], Coroutine]
):
    @wraps(f)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        telegram_id = update.effective_user.id
        app = context.application
        state = await repo.states.load_for_user(telegram_id, app)
        with Session.begin() as session:
            profile = get_profile(session, state.interpreter.role.label, state.user.id)
            state.interpreter.context.update(
                update=update, context=context, profile=profile
            )
            await f(update, context, state)
            await repo.states.save(state)

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
    if callback := await repo.callbacks.load(query.data):
        if callback.auto_answer:
            await query.answer()
        state.interpreter.context.update(query=query, callback=callback)
        await state.interpreter.dispatch_event("received callback query")
    else:
        await query.answer(text="This callback has expired")


@modifies_state
async def handle_photo(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    state: ProgramState,
) -> None:
    state.interpreter.context["message"] = update.effective_message
    state.interpreter.context["photo"] = update.effective_message.photo
    await state.interpreter.dispatch_event("received photo")


@modifies_state
async def handle_document(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    state: ProgramState,
) -> None:
    state.interpreter.context["message"] = update.effective_message
    state.interpreter.context["document"] = update.effective_message.document
    await state.interpreter.dispatch_event("received document")
