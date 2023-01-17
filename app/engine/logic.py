import asyncio
from typing import Any

from jinja2 import DictLoader, Environment
from telegram import InlineKeyboardButton, Message
from telegram.constants import ParseMode

from app.exceptions import ValidationError
from app.models import Answer, Callback, Content, ContentValidator, ProgramState
from app.models.role import Role
from app.repository import Repository

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


def get_answer(state: ProgramState) -> Any:
    answer = {
        ContentValidator(
            type=state.question.content_type,
            value=option.content.value,
        ).get_content()
        for option in state.selected_options.values()
    } | state.created_options
    answer = {content.value for content in answer}
    if state.question.allow_multiple_choices:
        return answer
    if answer:
        return answer.pop()


def expect(state: ProgramState, **inputs):
    state.inputs.update(
        {
            k: v if isinstance(v, ContentValidator) else ContentValidator(type=v)
            for k, v in inputs.items()
        }
    )


def release(state: ProgramState, *names: str):
    for name in names:
        state.inputs.pop(name, None)


async def make_inline_button(
    state: ProgramState, repo: Repository, name: str, **kwargs
) -> InlineKeyboardButton:
    callback = Callback(
        state_id=state.id,
        user_telegram_id=state.user.telegram_id,
        data=kwargs.pop("data", name),
        **kwargs,
    )
    await repo.callbacks.save(callback)
    return InlineKeyboardButton(name, callback_data=str(callback.id))


def clean_input(
    state: ProgramState,
    message: Message | None = None,
    callback: Callback | None = None,
) -> tuple[str, Content] | None:
    if not (message is None) ^ (callback is None):
        raise RuntimeError("either message or callback must be specified")
    # noinspection PyUnresolvedReferences
    text = message.text if callback is None else callback.data

    if not text:
        return

    for target, constraint in sorted(state.inputs.items(), key=lambda item: item[1]):
        validator = ContentValidator(
            type=constraint.type, value=text, options=constraint.options
        )
        try:
            validator.clean()
        except ValidationError:
            continue
        else:
            return target, validator.get_content()


async def save_answer(state: ProgramState, repo: Repository):
    answer = get_answer(state)
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
                    created_options=state.created_options,
                )
            )
        )


async def render_template(
    state: ProgramState, repo: Repository, template: str, **kwargs
) -> str:
    role: Role = state.interpreter.role
    templates = {"profile": role.profile_template, "__template__": template}
    loader = DictLoader(templates)
    environment = Environment(loader=loader, extensions=["jinja2.ext.do"])
    context = {
        "state": state,
        "user": state.user,
        "answers": state.answers,
        "profile": state.profile,
        **kwargs,
    }
    return environment.get_template("__template__").render(context)


async def render_question(state: ProgramState, repo: Repository) -> dict:
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
