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

from app.bot import (
    commands,
    get_cache,
    handle_callback_query,
    handle_command,
    handle_document,
    handle_message,
    handle_photo,
)
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
            statechart = await repo.statecharts.get(statechart_id)
            engine = BotInterpreter(app, statechart)
            task = asyncio.create_task(engine.run())


async def post_init(app: Application, *, update_trigger: asyncio.Event):
    asyncio.create_task(run_bot_logic(app, update_trigger=update_trigger))


async def run_user_logic(context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"running user logic, users={await repo.get_active_user_ids()}")
    for uid in await repo.get_active_user_ids():
        async with get_cache(uid, context.application) as cache:
            await cache.interpreter.dispatch_event("clock")


async def update_bot_config(context: ContextTypes.DEFAULT_TYPE):
    trigger: asyncio.Event = context.job.data["trigger"]
    settings.bot = await repo.bots.get(settings.bot_id)
    if not trigger.is_set():
        trigger.set()


async def handle_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(msg="Exception while handling an update:", exc_info=context.error)


async def initialize_bot():
    logger.info("Initializing the bot...")
    settings.bot = await repo.bots.get(settings.bot_id)
    logger.info("Using the following settings: ")
    logger.info(settings)


def main():
    loop = asyncio.get_event_loop()
    loop.run_until_complete(initialize_bot())

    update_trigger = asyncio.Event()
    app = (
        Application.builder()
        .token(settings.bot.token.get_secret_value())
        .post_init(partial(post_init, update_trigger=update_trigger))
        .build()
    )
    app.add_error_handler(handle_error)
    app.add_handlers(
        [
            *[CommandHandler(name, callback) for name, callback in commands.items()],
            MessageHandler(filters.COMMAND, handle_command),
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message),
            MessageHandler(filters.PHOTO, handle_photo),
            MessageHandler(filters.Document.ALL, handle_document),
            CallbackQueryHandler(handle_callback_query),
        ]
    )
    app.job_queue.run_repeating(
        run_user_logic,
        interval=settings.bot.user_clock_interval,
    )
    app.job_queue.run_repeating(
        update_bot_config,
        interval=settings.cache_ex_bot,
        data={"trigger": update_trigger},
    )
    logger.info("Polling has started UwU")
    app.run_polling()
