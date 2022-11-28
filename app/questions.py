from functools import partial
from operator import attrgetter

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
    target_action_skip_question = "skip question"
    target_action_save_answer = "save answer"
    target_action_create_option = "create option"

    def __init__(self, user: User):
        self.user: User = user
        self.question = (q := user.question)
        self.inline = q.is_multiple_choice or (
            q.is_single_choice and user.is_registered
        )

        key = "order" if all(choice.order > 0 for choice in q.options) else "name"
        self.options: list[Option] = sorted(q.options, key=attrgetter(key))
        for option in self.options:
            option.is_active = partial(self.is_option_selected, option)

    def is_option_selected(self, option: Option) -> bool:
        return option.id in self.user.selected_options.keys()

    def create_button(self, name: str, **kwargs):
        if self.inline:
            return self.user.make_inline_button(name, **kwargs)
        kwargs.pop("target", None)
        return KeyboardButton(name, **kwargs)

    def _create_markup(self, buttons: list[list]):
        if self.inline:
            return InlineKeyboardMarkup(buttons)
        if buttons:
            return ReplyKeyboardMarkup(buttons, resize_keyboard=True)
        return ReplyKeyboardRemove()

    def get_action(self, final: bool, skipped: bool) -> str:
        if final and skipped:
            return "Вопрос пропущен"
        if final:
            return "📩 Отправлено"
        if self.user.selected_options:
            return "Отправить"
        return "Ничего из перечисленного"

    def _create_choice_buttons(self) -> list[list]:
        btn = self.create_button

        buttons = []
        prev_big = False
        for option in self.options:
            button = btn(str(option), target=option.id)
            big = len(option) > settings.inline_half_width
            if buttons and len(buttons[-1]) == 1 and not prev_big and not big:
                buttons[-1].append(button)
            else:
                buttons.append([button])
            prev_big = big
        return buttons

    def get_text_options(self) -> list[str]:
        return [str(option) for option in self.options]

    def get_markup(
        self, final: bool = False, skipped: bool = False, extra: list[list[str]] = None
    ) -> InlineKeyboardMarkup:
        btn = self.create_button
        buttons = self._create_choice_buttons()

        # button with the action "custom choice"
        if self.question.is_customizable and not final:
            button = btn(
                self.question.text_action_create_option,
                target=self.target_action_create_option,
            )
            buttons.append([button])

        # add extra buttons
        if extra:
            buttons.extend(extra)

        # button "save" for questions with multiple choices
        if self.question.is_multiple_choice and self.is_answer_valid:
            action = self.get_action(final, skipped)
            button = btn(
                action, target=self.target_action_save_answer, auto_answer=False
            )
            buttons.append([button])

        # add the "skip" button
        if self.question.is_skippable and not self.user.selected_options:
            button = None
            if not final or final and self.question.is_single_choice and not skipped:
                button = btn(
                    self.question.text_action_skip_question,
                    target=self.target_action_skip_question,
                )
            if final and self.question.is_single_choice and skipped:
                button = btn(
                    f"✅ {self.question.text_action_skip_question}",
                    target=self.target_action_skip_question,
                )
            if button:
                buttons.append([button])

        # add the home button
        if not self.inline and (home := self.user.home_message):
            buttons.append([KeyboardButton(home)])

        return self._create_markup(buttons)

    def get_option(self, item: str) -> Option:
        for option in self.options:
            if item == (option.id if self.inline else str(option)):
                return option
        raise KeyError(
            f'Option with the {"id" if self.inline else "name"} {item} does not exist!'
        )

    def select_option(self, option: str | Option):
        if isinstance(option, str):
            option = self.get_option(option)
        if (uuid := option.id) in self.user.selected_options:
            del self.user.selected_options[uuid]
        else:
            self.user.selected_options[uuid] = option

    @property
    def total_choices(self) -> int:
        return len(self.user.selected_options.keys()) + len(self.user.created_options)

    @property
    def is_answer_valid(self) -> bool:
        if self.question.accept_empty_answers:
            return True
        return self.total_choices > 0

    def has_active_choices(self) -> bool:
        return len(self.user.selected_options) > 0
