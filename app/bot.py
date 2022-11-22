import sismic.model
from telegram import Update
from telegram.ext import ContextTypes

from app.models import User
from app.utils import get_logger, get_settings

__all__ = ["handle_message"]

logger = get_logger(__file__)
settings = get_settings()


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = await User.load(update.effective_user.id, context.application)
    user.interpreter.context.update(
        {"update": update, "context": context, "message": update.message}
    )
    await user.interpreter.dispatch_event(sismic.model.Event("message received"))
    await user.save()
