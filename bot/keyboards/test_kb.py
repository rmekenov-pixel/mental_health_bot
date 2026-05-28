from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove


def get_test_choice_keyboard() -> ReplyKeyboardMarkup:
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📋 PHQ-9 (Депрессия)")],
            [KeyboardButton(text="😰 GAD-7 (Тревожность)")],
            [KeyboardButton(text="🔥 Burnout (Выгорание)")],
            [KeyboardButton(text="💛 Самооценка")],
            [KeyboardButton(text="🧠 Эмоциональный интеллект")],
        ],
        resize_keyboard=True
    )
    return keyboard


def get_answer_keyboard() -> ReplyKeyboardMarkup:
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Никогда (0)"), KeyboardButton(text="Очень редко (1)")],
            [KeyboardButton(text="Редко (2)"), KeyboardButton(text="Иногда (3)")],
            [KeyboardButton(text="Часто (4)"), KeyboardButton(text="Очень часто (5)")],
            [KeyboardButton(text="Каждый день (6)")],
        ],
        resize_keyboard=True
    )
    return keyboard

def get_phq_gad_keyboard() -> ReplyKeyboardMarkup:
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

def get_eq_keyboard() -> ReplyKeyboardMarkup:
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Совсем не согласен (1)")],
            [KeyboardButton(text="Скорее не согласен (2)")],
            [KeyboardButton(text="Нейтрально (3)")],
            [KeyboardButton(text="Скорее согласен (4)")],
            [KeyboardButton(text="Полностью согласен (5)")],
        ],
        resize_keyboard=True
    )
    return keyboard


def get_main_keyboard() -> ReplyKeyboardMarkup:
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🧪 Пройти тест")],
            [KeyboardButton(text="📊 Моя история"), KeyboardButton(text="✅ Чек-ин")],
            [KeyboardButton(text="📈 График"), KeyboardButton(text="🔍 Инсайты")],
            [KeyboardButton(text="📅 Календарь"), KeyboardButton(text="💬 Обратная связь")],
        ],
        resize_keyboard=True
    )
    return keyboard

def remove_keyboard() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()