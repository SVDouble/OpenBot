from telegram import Update
from telegram.ext import ContextTypes

from app.integrations.telegram.utils import modifies_state
from app.models import Cache
from app.utils import get_logger, get_repository, get_settings

__all__ = [
    "handle_message",
    "handle_command",
    "handle_callback_query",
    "handle_document",
    "handle_photo",
]

logger = get_logger(__file__)
settings = get_settings()
repo = get_repository()


@modifies_state
async def handle_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    cache: Cache,
) -> None:
    cache.interpreter.context["message"] = update.effective_message
    await cache.interpreter.dispatch_event("received message")


@modifies_state
async def handle_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    cache: Cache,
) -> None:
    message = update.effective_message
    command = message.text[1 : message.entities[0].length]
    args = message.text[message.entities[0].length + 1 :].split()
    cache.interpreter.context.update(message=message, command=command, args=args)
    await cache.interpreter.dispatch_event("received command")


@modifies_state
async def handle_callback_query(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    cache: Cache,
) -> None:
    query = update.callback_query
    if callback := await repo.callbacks.load(query.data):
        if callback.auto_answer:
            await query.answer()
        cache.interpreter.context.update(query=query, callback=callback)
        await cache.interpreter.dispatch_event("received callback query")
    else:
        await query.answer(text="This callback has expired")


@modifies_state
async def handle_photo(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    cache: Cache,
) -> None:
    cache.interpreter.context["message"] = update.effective_message
    cache.interpreter.context["photo"] = update.effective_message.photo
    await cache.interpreter.dispatch_event("received photo")


@modifies_state
async def handle_document(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    cache: Cache,
) -> None:
    cache.interpreter.context["message"] = update.effective_message
    cache.interpreter.context["document"] = update.effective_message.document
    await cache.interpreter.dispatch_event("received document")
