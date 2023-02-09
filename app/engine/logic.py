import asyncio
from typing import Any

from jinja2 import DictLoader, Environment
from telegram import Document, InlineKeyboardButton, Message, PhotoSize
from telegram.constants import ParseMode

from app.exceptions import ValidationError
from app.models import Answer, Cache, Callback, Content, ContentValidator, User
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
    "render_question",
]

logger = get_logger(__file__)


async def get_answer(
    state: Cache, question_label: str, *, key: str | None = None
) -> Any:
    if state.question and state.question.label == question_label:
        contents = [
            await ContentValidator(
                type=state.question.content_type,
                value=option.content.value,
            ).get_content()
            for option in state.selected_options.values()
        ] + state.created_options
        values = [content.value for content in contents]
        answer = {
            "value": values,
            "option": set(state.selected_options.keys()),
            "label": set(option.label for option in state.selected_options.values()),
            "is_multivalued": state.question.allow_multiple_choices,
        }
    else:
        answer = state.answers[question_label]

    if key is not None:
        data = answer[key]
        if not answer["is_multivalued"]:
            data = data.pop() if data else None
        return data
    return answer


def expect(state: Cache, **inputs):
    state.inputs.update(
        {
            k: v if isinstance(v, ContentValidator) else ContentValidator(type=v)
            for k, v in inputs.items()
        }
    )


def release(state: Cache, *names: str):
    for name in names:
        state.inputs.pop(name, None)


async def make_inline_button(
    state: Cache, repo: Repository, name: str, **kwargs
) -> InlineKeyboardButton:
    callback = Callback(
        state_id=state.id,
        user_telegram_id=state.user.telegram_id,
        data=kwargs.pop("data", name),
        **kwargs,
    )
    await repo.callbacks.save(callback)
    return InlineKeyboardButton(name, callback_data=str(callback.id))


async def clean_input(
    state: Cache,
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

    for target, constraint in sorted(state.inputs.items(), key=lambda item: item[1]):
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


async def save_answer(state: Cache, repo: Repository):
    answer = await get_answer(state, state.question.label)
    state.answers[state.question.label] = answer
    if trait := state.question.user_trait:
        setattr(state.profile, trait.column, answer)
        asyncio.create_task(
            repo.answers.create(
                Answer(
                    owner=state.user.id,
                    question=state.question.id,
                    user_trait=trait.id,
                    selected_options=list(state.selected_options.keys()),
                    created_options=[
                        Content(
                            **(
                                content.dict(exclude_none=True)
                                | {"owner": state.user.id}
                            )
                        )
                        for content in state.created_options
                    ],
                )
            )
        )
    return answer


async def render_template(
    state: Cache, repo: Repository, template_: str, **kwargs
) -> str:
    loader = DictLoader({"__template__": template_})
    environment = Environment(
        loader=loader, extensions=["jinja2.ext.do"], enable_async=True
    )
    context = {
        "state": state,
        "user": state.user,
        "answers": state.answers,
        "profile": state.profile,
        "context": state.context,
        **kwargs,
    }

    async def render_profile(user: User) -> str:
        role = await repo.roles.get(user.role)
        profile_template = environment.from_string(role.profile_template)
        return await profile_template.render_async(context)

    async def render(obj: Any):
        if isinstance(obj, User):
            return await render_profile(obj)
        raise RuntimeError(f"Cannot render a '{type(obj).__name__}'")

    environment.filters["render"] = render
    template = environment.get_template("__template__")
    return await template.render_async(context)


async def render_question(state: Cache, repo: Repository) -> dict:
    photos: list[str] = []
    text = await render_template(
        state,
        repo,
        state.question.name,
        load_photo=lambda content_id: photos.append(content_id),
    )
    photos = [
        photo.value
        for content_id in photos
        if (photo := await repo.contents.get(content_id))
    ]
    if photos:
        # TODO: support multiple photos
        return {
            "photo": photos[0],
            "caption": text,
            "parse_mode": ParseMode.HTML,
        }
    else:
        return {
            "text": text,
            "parse_mode": ParseMode.HTML,
        }
