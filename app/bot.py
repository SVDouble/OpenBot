from telegram import Update
from telegram.ext import ContextTypes

from app.models import User
from app.settings import get_settings
from app.utils import get_logger

__all__ = ["handle_message"]

logger = get_logger(__file__)
settings = get_settings()


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Echo the user message."""
    await update.message.reply_text(update.message.text)
    user = await User.load(update.effective_user.id, context.application)
    await user.save()
