from functools import partial
from itertools import chain
from typing import Any

from telegram import (
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

__all__ = ["QuestionManager"]

from app.models import User, Option
from app.utils import get_logger, get_settings

logger = get_logger(__name__)
settings = get_settings()


class QuestionManager:
    action_skip_question = "skip question"
    action_save_answer = "save answer"
    action_create_option = "create option"

    def __init__(self, user: User):
        self.user: User = user
        self.question = user.question
        self.is_inline = user.question.allow_multiple_choices or user.is_registered
        self.option_markup: list[list[Option]] = user.question.options
        self.options: list[Option] = list(chain.from_iterable(self.option_markup))
        for option in self.options:
            option.is_active = partial(self.is_option_selected, option)

    def is_option_selected(self, option: Option) -> bool:
        return option.id in self.user.selected_options.keys()

    async def create_button(self, name: str, data: Any, **kwargs):
        if self.is_inline:
            return await self.user.make_inline_button(name, data=data, **kwargs)
        return KeyboardButton(name, **kwargs)

    def _create_markup(self, buttons: list[list]):
        if self.is_inline:
            return InlineKeyboardMarkup(buttons)
        if buttons:
            return ReplyKeyboardMarkup(buttons, resize_keyboard=True)
        return ReplyKeyboardRemove()

    def get_action(self, is_final: bool, is_skipped: bool) -> str:
        if is_final and is_skipped:
            return "Вопрос пропущен"
        if is_final:
            return "📩 Отправлено"
        if self.user.selected_options:
            return "Отправить"
        return "Ничего из перечисленного"

    async def _create_choice_buttons(self) -> list[list]:
        return [
            [
                await self.create_button(str(option), data=str(option.id))
                for option in row
            ]
            for row in self.option_markup
        ]

    def get_options(self) -> list[str]:
        return [str(option.id if self.is_inline else option) for option in self.options]

    async def get_markup(
        self, is_final: bool = False, is_skipped: bool = False
    ) -> InlineKeyboardMarkup:
        buttons = await self._create_choice_buttons()

        # button "save" for questions with multiple choices
        if self.question.allow_multiple_choices and self.is_answer_valid:
            action = self.get_action(is_final, is_skipped)
            button = await self.create_button(action, data=self.action_save_answer)
            buttons.append([button])

        # button "skip"
        if (
            self.question.allow_skipping
            and self.user.total_choices == 0
            and not is_final
        ):
            skip_button = await self.create_button(
                self.question.text_skip,
                data=self.action_skip_question,
            )
            buttons.append([skip_button])

        return self._create_markup(buttons)

    def parse_option(self, item: str) -> Option:
        for option in self.options:
            if item == str(option.id if self.is_inline else option):
                return option
        raise KeyError(
            f'Option with the {"id" if self.is_inline else "name"} '
            f"{item} does not exist!"
        )

    def toggle_option(self, option: str | Option):
        if isinstance(option, str):
            option = self.parse_option(option)
        if (uuid := option.id) in self.user.selected_options:
            del self.user.selected_options[uuid]
        else:
            self.user.selected_options[uuid] = option

    @property
    def is_answer_valid(self) -> bool:
        if self.question.allow_empty_answers:
            return True
        return self.user.total_choices > 0
