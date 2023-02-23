import contextlib
import datetime
import html
import io
import json
from functools import wraps
from typing import Callable, Coroutine

import jinja2
import telegram
from httpx import HTTPStatusError
from pydantic.json import pydantic_encoder
from sqlalchemy import Column, Table, text
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, ContextTypes

from app.engine.logic import render_template
from app.models import Cache
from app.profile import Session, content_type_to_column, get_profile, get_profile_class
from app.utils import get_logger, get_repository, get_settings

__all__ = [
    "handle_message",
    "handle_command",
    "handle_callback_query",
    "handle_document",
    "handle_photo",
    "commands",
    "get_cache",
]

logger = get_logger(__file__)
settings = get_settings()
repo = get_repository()


@contextlib.asynccontextmanager
async def get_cache(telegram_id: int, app: Application):
    cache = await repo.caches.load_for_user(telegram_id, app)
    with Session.begin() as session:
        cache.session = session
        profile = get_profile(session, cache.interpreter.role.label, cache.user.id)
        cache.interpreter.context.update(profile=profile)
        yield cache
        await repo.caches.save(cache)
        state = cache.modify_state(await repo.states.get(cache.id))
        try:
            await repo.states.patch(state)
        except HTTPStatusError:
            await app.bot.send_message(
                telegram_id, "We've reset your account, so you can start anew"
            )
            await repo.users.remove(cache.user)
        else:
            await repo.users.patch(cache.user)
        cache.session = None


def modifies_state(f: Callable[[Update, ContextTypes.DEFAULT_TYPE, Cache], Coroutine]):
    @wraps(f)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        async with get_cache(update.effective_user.id, context.application) as cache:
            cache.interpreter.context.update(update=update, context=context)
            await f(update, context, cache)

    return wrapper


# commands


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cache = await repo.caches.load_for_user(
        update.effective_user.id, context.application
    )
    await repo.caches.remove(cache)
    await update.message.reply_text("done")


async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("pong")


async def dump_cache(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        arg = context.args.pop()
    except IndexError:
        keys = {"state"} | set(Cache.__fields__.keys())
        await update.message.reply_text(
            f"Please specify an attribute to show; possible values: {keys}",
        )
        return
    cache = await repo.caches.load_for_user(
        update.effective_user.id, context.application
    )
    if arg == "state":
        data = cache.interpreter.configuration
    else:
        data = cache.dict(exclude_none=True).get(arg, None)
    data = json.dumps(data, default=pydantic_encoder, ensure_ascii=False, indent=4)
    if len(data) > 4000:
        filename = f"{arg}_{str(cache.user.id)[:8]}_{datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S')}.json"
        await update.message.reply_document(io.StringIO(data), filename=filename)
    else:
        await update.message.reply_text(
            f"<code>{html.escape(data)}</code>",
            parse_mode=ParseMode.HTML,
        )


async def sync_database(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sync database with the current roles configuration"""
    roles = await repo.roles.get(many=True)
    if not roles:
        await update.message.reply_text("No roles found")
        return

    def add_column(table_name_, column_):
        # column_name_ = column_.compile(dialect=session.bind.dialect)
        column_type_ = column_.type.compile(session.bind.dialect)
        # TODO: prevent possible sql injections? use alembic instead?
        session.execute(
            text(
                'ALTER TABLE "%s" ADD COLUMN "%s" %s'
                % (table_name_, column_.name, column_type_)
            )
        )

    with Session.begin() as session:
        for role in roles:
            profile_class = get_profile_class(role.label)
            stats = f"{role.name} ({session.query(profile_class).count()} objects): \n"
            for trait in role.traits:
                table: Table = profile_class.__table__
                column_name = trait.column
                is_new = False
                if column_name not in table.columns.keys():
                    is_new = True
                    logger.info(
                        f"Adding column {column_name!r} to the {table.name!r} table"
                    )
                    type_ = content_type_to_column[trait.type]
                    column = Column(column_name, type_, nullable=True)
                    table.append_column(column)
                    add_column(table.name, column)
                sign = "+" if is_new else "-"
                stats += f"  {sign} {column_name} ({trait.type.value})\n"
            await update.message.reply_text(stats)


@modifies_state
async def render_template_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    cache: Cache,
) -> None:
    template = update.message.text.removeprefix("/render").strip()
    if not template:
        await update.message.reply_text("Please specify a template to render")
        return
    try:
        message_kwargs = await render_template(cache, repo, template, is_extended=True)
    except jinja2.exceptions.TemplateSyntaxError as e:
        await update.message.reply_text(
            f"Syntax error in template: {e.message} at line {e.lineno}"
        )
    except jinja2.exceptions.TemplateError as e:
        await update.message.reply_text(f"Error while rendering template: {e.message}")
    else:
        try:
            await update.message.reply_text(**message_kwargs, parse_mode=ParseMode.HTML)
        except telegram.error.BadRequest as e:
            await update.message.reply_text(
                f"Error while rendering template: {e.message}"
            )


commands = {
    "reset": reset,
    "ping": ping,
    "dump": dump_cache,
    "syncdb": sync_database,
    "render": render_template_command,
}


# handlers


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
    args = context.args
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
