from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove


def get_test_choice_keyboard() -> ReplyKeyboardMarkup:
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📋 PHQ-9 (Депрессия)")],
            [KeyboardButton(text="😰 GAD-7 (Тревожность)")],
        ],
        resize_keyboard=True
    )
    return keyboard


def get_answer_keyboard() -> ReplyKeyboardMarkup:
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Совсем нет (0)")],
            [KeyboardButton(text="Несколько дней (1)")],
            [KeyboardButton(text="Больше половины дней (2)")],
            [KeyboardButton(text="Почти каждый день (3)")],
        ],
        resize_keyboard=True
    )
    return keyboard


def get_main_keyboard() -> ReplyKeyboardMarkup:
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🧪 Пройти тест")],
            [KeyboardButton(text="📊 Моя история"), KeyboardButton(text="✅ Чек-ин")],
            [KeyboardButton(text="📈 График")],
        ],
        resize_keyboard=True
    )
    return keyboard


def remove_keyboard() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()