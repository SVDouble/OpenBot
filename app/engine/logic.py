import asyncio
from typing import Any
from uuid import UUID

from jinja2 import DictLoader, Environment
from sqlalchemy.dialects.postgresql import Range
from telegram import Chat, Document, InlineKeyboardButton, Message, PhotoSize
from telegram.ext import Application

from app.exceptions import ValidationError
from app.models import (
    Answer,
    Cache,
    Callback,
    Content,
    ContentType,
    ContentValidator,
    User,
)
from app.profile import get_profile
from app.repository import Repository
from app.utils import get_logger

__all__ = [
    "get_answer",
    "expect",
    "release",
    "make_inline_button",
    "clean_input",
    "save_answer",
    "render_template",
    "get_chat",
    "get_user_profile",
]

logger = get_logger(__file__)


async def get_answer(
    cache: Cache, question_label: str, *, key: str | None = None
) -> Any:
    question = cache.question
    if question and question.label == question_label:
        contents = [
            opt.content for opt in cache.selected_options.values()
        ] + cache.created_options
        answer = {
            "value": [content.value for content in contents],
            "choice": set(cache.selected_options.keys()),
            "label": set(option.label for option in cache.selected_options.values()),
            "name": set(option.name for option in cache.selected_options.values()),
        }
        is_multivalued = question.allow_multiple_choices
        if question.user_trait:
            is_multivalued |= question.user_trait.is_multivalued
        if not is_multivalued:
            answer = {k: next(iter(v), None) for k, v in answer.items()}
    else:
        answer = cache.answers[question_label]

    if key is not None:
        return answer[key]
    return answer


def expect(cache: Cache, **inputs):
    cache.inputs.update(
        {
            k: v if isinstance(v, ContentValidator) else ContentValidator(type=v)
            for k, v in inputs.items()
        }
    )


def release(cache: Cache, *names: str):
    for name in names:
        cache.inputs.pop(name, None)


async def make_inline_button(
    cache: Cache, repo: Repository, name: str, **kwargs
) -> InlineKeyboardButton:
    callback = Callback(
        state_id=cache.id,
        user_telegram_id=cache.user.telegram_id,
        data=kwargs.pop("data", name),
        **kwargs,
    )
    await repo.callbacks.save(callback)
    return InlineKeyboardButton(name, callback_data=str(callback.id))


async def clean_input(
    cache: Cache,
    message: Message | None = None,
    callback: Callback | None = None,
    photo: tuple[PhotoSize, ...] | None = None,
    document: Document | None = None,
) -> tuple[str, Content] | None:
    if message is not None:
        value = message.text
    elif callback:
        value = callback.data
    elif photo:
        value = photo[-1]
    elif document:
        value = document
    else:
        raise RuntimeError("At least one source must be specified")

    for target, constraint in sorted(cache.inputs.items(), key=lambda item: item[1]):
        validator = ContentValidator(
            type=constraint.type,
            value=value,
            options=constraint.options,
        )
        try:
            validator.clean()
        except ValidationError:
            continue
        else:
            return target, await validator.get_content()


async def save_answer(cache: Cache, repo: Repository):
    data = await get_answer(cache, cache.question.label)
    cache.answers[cache.question.label] = data
    if trait := cache.question.user_trait:
        if trait.type is ContentType.DATE_RANGE:
            value = Range(**data["value"])
        elif trait.type is ContentType.NUMBER_RANGE:
            value = Range(**data["value"])
        else:
            value = data["value"]
        setattr(cache.profile, trait.column, value)
        selected_options = [
            opt.id for opt in cache.selected_options.values() if not opt.is_dynamic
        ]
        dynamic_contents = [
            opt.content for opt in cache.selected_options.values() if opt.is_dynamic
        ]
        created_options = [
            Content(**(content.dict(exclude_none=True) | {"owner": cache.user.id}))
            for content in cache.created_options + dynamic_contents
        ]
        answer = Answer(
            owner=cache.user.id,
            question=cache.question.id,
            user_trait=trait.id,
            selected_options=selected_options,
            created_options=created_options,
        )
        asyncio.create_task(repo.answers.create(answer))
    return data


async def get_user_profile(cache: Cache, repo: Repository, user: User):
    role = await repo.roles.get(user.role)
    return get_profile(cache.session, role.label, user.id)


async def render_template(
    cache: Cache, repo: Repository, template_: str, is_extended: bool = False, **kwargs
) -> str | dict:
    loader = DictLoader({"__template__": template_})
    environment = Environment(
        loader=loader, extensions=["jinja2.ext.do"], enable_async=True
    )
    context = {
        "cache": cache,
        "user": cache.user,
        "answers": cache.answers,
        "profile": cache.profile,
        **cache.context,
        **kwargs,
    }

    photos: list[str] = []

    async def render_photo(photo: str):
        if not photo:
            return ""
        try:
            content_id = UUID(photo)
        except ValueError:
            photos.append(photo)
        else:
            content = await repo.contents.get(content_id)
            if content and (value := content.value):
                photos.append(value)
        return ""

    async def render_profile(user: User, profile) -> str:
        role = await repo.roles.get(user.role)
        profile_template = environment.from_string(role.profile_template)
        render_context = {"user": user, "profile": profile}
        return await profile_template.render_async(render_context)

    async def render(obj: Any):
        if isinstance(obj, User):
            if obj.id == cache.user.id:
                profile = cache.profile
            else:
                profile = await get_user_profile(cache, repo, obj)
            return await render_profile(obj, profile)
        raise RuntimeError(f"Cannot render a '{type(obj).__name__}'")

    environment.filters["render"] = render
    environment.filters["render_photo"] = render_photo
    template = environment.get_template("__template__")
    text = await template.render_async(context)
    if is_extended:
        if photos:
            # TODO: support multiple photos
            return {"photo": photos[0], "caption": text}
        else:
            return {"text": text}
    else:
        return text


async def get_chat(app: Application, target: User | int) -> Chat:
    if isinstance(target, User):
        target = target.telegram_id
    return await app.bot.get_chat(target)
