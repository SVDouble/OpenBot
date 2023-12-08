import datetime
import html
import io
import json

import jinja2
import telegram
from pydantic.json import pydantic_encoder
from sqlalchemy import Column, Table, text
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from app.engine.logic import render_template
from app.integrations.telegram.utils import modifies_state
from app.models import Cache
from app.profile import Session, content_type_to_column, get_profile_class
from app.utils import get_logger, get_repository, get_settings

__all__ = [
    "reset",
    "ping",
    "dump_cache",
    "sync_database",
    "render_template_command",
]

logger = get_logger(__file__)
settings = get_settings()
repo = get_repository()


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cache = await repo.caches.load_for_user(
        update.effective_user.id, context.application
    )
    await repo.states.delete(cache.user.state)
    await repo.users.remove(cache.user)
    await repo.caches.remove(cache)
    await update.message.reply_text("done")


async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("pong")


async def dump_cache(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        arg = context.args.pop()
    except IndexError:
        keys = {"state"} | set(Cache.model_fields.keys())
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
