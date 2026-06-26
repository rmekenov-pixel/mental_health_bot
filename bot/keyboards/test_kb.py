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
        resize_keyboard=True
    )
    return keyboard


def get_options_keyboard(options: list[str]) -> ReplyKeyboardMarkup:
    """Builds a reply keyboard from a test's options list (one button per row,
    or two per row if there are many short options). Options come straight
    from the test JSON file for the given language, so the button text always
    matches the language of the questions."""
    rows = [[KeyboardButton(text=option)] for option in options]
    keyboard = ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True
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
        resize_keyboard=True
    )
    return keyboard

def remove_keyboard() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()
