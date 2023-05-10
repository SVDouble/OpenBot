from functools import wraps
from typing import Callable, Coroutine

from telegram import Update
from telegram.ext import ContextTypes

from app.integrations.utils import get_cache
from app.models import Cache
from app.utils import get_repository

__all__ = ["modifies_state"]

repo = get_repository()


def modifies_state(f: Callable[[Update, ContextTypes.DEFAULT_TYPE, Cache], Coroutine]):
    @wraps(f)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        async with get_cache(update.effective_user.id, context.application) as cache:
            cache.interpreter.context.update(tg_update=update, tg_context=context)
            await f(update, context, cache)

    return wrapper
