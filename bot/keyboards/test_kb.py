from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from bot.services.localization import t


def get_test_choice_keyboard(lang: str = "ru") -> ReplyKeyboardMarkup:
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t(lang, "test_btn_phq9"))],
            [KeyboardButton(text=t(lang, "test_btn_gad7"))],
            [KeyboardButton(text=t(lang, "test_btn_burnout"))],
            [KeyboardButton(text=t(lang, "test_btn_self_esteem"))],
            [KeyboardButton(text=t(lang, "test_btn_eq"))],
        ],
        resize_keyboard=True,
        is_persistent=True
    )
    return keyboard


def get_options_keyboard(options: list[str]) -> ReplyKeyboardMarkup:
    """Строит клавиатуру вариантов ответа с принудительным отображением в клиенте."""
    rows = [[KeyboardButton(text=option)] for option in options]
    keyboard = ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
        is_persistent=True
    )
    return keyboard


def get_main_keyboard(lang: str = "ru") -> ReplyKeyboardMarkup:
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t(lang, "btn_test"))],
            [KeyboardButton(text=t(lang, "btn_history")), KeyboardButton(text=t(lang, "btn_checkin"))],
            [KeyboardButton(text=t(lang, "btn_chart")), KeyboardButton(text=t(lang, "btn_insights"))],
            [KeyboardButton(text=t(lang, "btn_calendar")), KeyboardButton(text=t(lang, "btn_feedback"))],
        ],
        resize_keyboard=True,
        is_persistent=True
    )
    return keyboard


def remove_keyboard() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()
