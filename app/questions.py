from collections import defaultdict
from typing import Any

from telegram import (
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

__all__ = ["QuestionManager"]

from app.engine.logic import make_inline_button
from app.models import Cache, Option
from app.repository import Repository
from app.utils import get_logger, get_settings

logger = get_logger(__name__)
settings = get_settings()


class QuestionManager:
    action_skip_question = "skip question"
    action_save_answer = "save answer"
    action_create_option = "create option"

    def __init__(self, state: Cache, repo: Repository):
        self.state = state
        self.repo = repo
        self.question = state.question
        self.options: list[Option] = self.question.options
        self.option_layout: list[list[Option]] = self._generate_option_layout(
            self.question.options
        )
        self.is_inline = self.question.allow_multiple_choices
        for option in self.options:
            option.is_active = option.id in state.selected_options.keys()

    @staticmethod
    def _generate_option_layout(options: list[Option]) -> list[list[Option]]:
        layout = defaultdict(dict)
        for option in options:
            layout[option.row][option.column] = option
        return [
            [layout[row][column] for column in sorted(layout[row].keys())]
            for row in sorted(layout.keys())
        ]

    async def create_button(self, name: str, data: Any, **kwargs):
        if self.is_inline:
            return await make_inline_button(
                self.state, self.repo, name, data=data, **kwargs
            )
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
        if self.state.selected_options:
            return "Отправить"
        return "Ничего из перечисленного"

    async def _create_choice_buttons(self) -> list[list]:
        return [
            [
                await self.create_button(str(option), data=str(option.id))
                for option in row
            ]
            for row in self.option_layout
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
            and self.state.total_choices == 0
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

    async def toggle_option(self, option: str | Option):
        if isinstance(option, str):
            option = self.parse_option(option)
        if (uuid := option.id) in self.state.selected_options:
            del self.state.selected_options[uuid]
        else:
            self.state.selected_options[uuid] = option
        option.is_active = not option.is_active

    @property
    def is_answer_valid(self) -> bool:
        if self.question.allow_empty_answers:
            return True
        return self.state.total_choices > 0
