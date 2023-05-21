import asyncio
import datetime
from functools import partial
from uuid import UUID

import telegram
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import app.integrations.telegram.commands as commands
import app.integrations.telegram.handlers as handlers
from app.integrations.utils import get_cache
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
    if bot := await repo.bots.get(settings.bot_id):
        settings.bot = bot
        if not trigger.is_set():
            trigger.set()


async def disable_inactive_users(context: ContextTypes.DEFAULT_TYPE):
    for user in await repo.users.get(is_active=True, many=True):
        try:
            await context.bot.send_chat_action(
                chat_id=user.telegram_id, action=ChatAction.TYPING
            )
        except telegram.error.TelegramError as e:
            if isinstance(e, telegram.error.Forbidden):
                user.is_matchable = False
                await repo.users.patch(user)
                logger.debug(
                    f"Deactivated user {user.telegram_id} (typing test: '{e}')"
                )


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
            CommandHandler("reset", commands.reset),
            CommandHandler("ping", commands.ping),
            CommandHandler("dump", commands.dump_cache),
            CommandHandler("syncdb", commands.sync_database),
            CommandHandler("render", commands.render_template_command),
            MessageHandler(filters.COMMAND, handlers.handle_command),
            MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.handle_message),
            MessageHandler(filters.PHOTO, handlers.handle_photo),
            MessageHandler(filters.Document.ALL, handlers.handle_document),
            CallbackQueryHandler(handlers.handle_callback_query),
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
    if settings.check_user_inactivity:
        app.job_queue.run_repeating(
            disable_inactive_users,
            # first=settings.check_user_inactivity_time,
            first=datetime.datetime.now() + datetime.timedelta(seconds=10),
            interval=datetime.timedelta(days=1),
        )
    logger.info("Polling has started UwU")
    app.run_polling()
