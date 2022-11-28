import asyncio

from telegram.ext import (
    Application,
    MessageHandler,
    filters,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
)

from app.bot import handle_message, commands, handle_command, handle_callback_query
from app.models import StateChart, User
from app.utils import get_logger, get_settings, get_repository

logger = get_logger(__file__)
settings = get_settings()
repo = get_repository()


async def run_engine_logic(app: Application):
    from app.engine import BotInterpreter

    statechart = StateChart.load(settings.bot_statechart_source)
    engine = BotInterpreter(app, statechart)
    asyncio.create_task(engine.run())


async def run_user_logic(app: Application):
    logger.info(f"running user logic, users={await repo.get_user_ids()}")
    for uid in await repo.get_user_ids():
        user = await User.load(uid, app)
        await user.interpreter.dispatch_event("clock")


async def handle_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(msg="Exception while handling an update:", exc_info=context.error)


def main():
    app = (
        Application.builder()
        .token(settings.bot_token)
        .post_init(run_engine_logic)
        .build()
    )
    app.add_error_handler(handle_error)
    app.add_handlers(
        [
            *[CommandHandler(name, callback) for name, callback in commands.items()],
            MessageHandler(filters.COMMAND, handle_command),
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message),
            CallbackQueryHandler(handle_callback_query),
        ]
    )
    app.job_queue.run_repeating(run_user_logic, interval=settings.user_clock_interval)
    app.run_polling()
