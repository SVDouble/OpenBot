import asyncio

from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from app.bot import commands, handle_callback_query, handle_command, handle_message
from app.models import Statechart, ProgramState
from app.utils import get_logger, get_repository, get_settings

logger = get_logger(__file__)
settings = get_settings()
repo = get_repository()


async def run_engine_logic(app: Application):
    from app.engine import BotInterpreter

    statechart = Statechart.load(settings.bot_statechart_source)
    engine = BotInterpreter(app, statechart)
    asyncio.create_task(engine.run())


async def run_user_logic(app: Application):
    from app.profile import reload_profile_class

    logger.info(f"running user logic, users={await repo.get_user_ids()}")
    reload_profile_class()
    for uid in await repo.get_user_ids():
        user = await ProgramState.load(uid, app)
        await user.interpreter.dispatch_event("clock")


async def handle_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(msg="Exception while handling an update:", exc_info=context.error)


def main():
    app = (
        Application.builder()
        .token(settings.bot.token)
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
    app.job_queue.run_repeating(
        run_user_logic, interval=settings.bot.user_clock_interval
    )
    app.run_polling()
