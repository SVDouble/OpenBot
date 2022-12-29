import asyncio
from functools import partial
from uuid import UUID

from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from app.bot import commands, handle_callback_query, handle_command, handle_message
from app.models import ProgramState
from app.utils import get_logger, get_repository, get_settings

logger = get_logger(__file__)
settings = get_settings()
repo = get_repository()


async def run_bot_logic(app: Application, *, update_trigger: asyncio.Event):
    from app.engine import BotInterpreter

    # TODO: bot data persistence?

    task: asyncio.Task | None = None
    statechart_id: UUID | None = None
    engine: BotInterpreter | None = None

    while True:
        await update_trigger.wait()
        update_trigger.clear()
        old_statechart_id = statechart_id
        statechart_id = settings.bot.statechart
        if statechart_id == old_statechart_id:
            continue
        if task:
            await engine.stop()
            await task
            task = None
        if statechart_id:
            statechart = await repo.get_statechart(statechart_id)
            engine = BotInterpreter(app, statechart)
            task = asyncio.create_task(engine.run())


async def run_user_logic(app: Application):
    from app.profile import reload_profile_class

    logger.info(f"running user logic, users={await repo.get_user_ids()}")
    reload_profile_class()
    for uid in await repo.get_user_ids():
        state = await ProgramState.load(uid, app)
        await state.interpreter.dispatch_event("clock")


async def update_bot_config(_: Application, trigger: asyncio.Event):
    settings.bot = await repo.get_bot(settings.bot.id)
    if not trigger.is_set():
        trigger.set()


async def handle_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(msg="Exception while handling an update:", exc_info=context.error)


def main():
    update_trigger = asyncio.Event()
    app = (
        Application.builder()
        .token(settings.bot.token)
        .post_init(partial(run_bot_logic), update_trigger=update_trigger)
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
        run_user_logic,
        interval=settings.bot.user_clock_interval,
    )
    app.job_queue.run_repeating(
        update_bot_config,
        interval=settings.cache_ex_bots,
        job_kwargs={"trigger": update_trigger},
    )
    app.run_polling()
