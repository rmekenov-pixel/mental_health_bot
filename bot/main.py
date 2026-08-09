import asyncio
import logging
from aiogram import Bot, Dispatcher, BaseMiddleware
from aiogram.types import TelegramObject
from aiogram.fsm.storage.memory import MemoryStorage
from bot.config import BOT_TOKEN
from bot.handlers import start, tests, history, checkin, charts, feedback, admin, calendar, language
from bot.services.reminders import setup_scheduler
from bot.services.localization import load_locale
from database.db import init_db
from typing import Callable, Dict, Any, Awaitable

logging.basicConfig(level=logging.INFO)

# Built from the locale files instead of being hardcoded, so it always stays
# in sync with whatever button text lives in locales/*.json — including the
# test-choice buttons (PHQ-9, GAD-7, etc.), which also need a state reset.
_MENU_BUTTON_KEYS = [
    "btn_test", "btn_history", "btn_checkin", "btn_chart",
    "btn_insights", "btn_calendar", "btn_feedback",
    "test_btn_phq9", "test_btn_gad7", "test_btn_burnout",
    "test_btn_self_esteem", "test_btn_eq",
]

MAIN_MENU_BUTTONS = []
for _lang in ("ru", "kz", "en"):
    _locale = load_locale(_lang)
    for _key in _MENU_BUTTON_KEYS:
        if _key in _locale:
            MAIN_MENU_BUTTONS.append(_locale[_key])

MAIN_MENU_BUTTONS += ["🇷🇺 Русский", "🇰🇿 Қазақша", "🇬🇧 English"]


class ResetStateMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        state = data.get("state")
        if state and hasattr(event, 'text') and event.text:
            # Сбрасываем при кнопках меню
            if event.text in MAIN_MENU_BUTTONS:
                await state.clear()
            # Сбрасываем при командах кроме /start (он сам сбрасывает)
            elif event.text.startswith('/') and event.text != '/start':
                current = await state.get_state()
                if current and 'ReminderStates' in current:
                    await state.clear()
        return await handler(event, data)


async def main():
    await init_db()

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    dp.message.middleware(ResetStateMiddleware())

    dp.include_router(start.router)
    dp.include_router(tests.router)
    dp.include_router(history.router)
    dp.include_router(checkin.router)
    dp.include_router(charts.router)
    dp.include_router(feedback.router)
    dp.include_router(admin.router)
    dp.include_router(calendar.router)
    dp.include_router(language.router)

    from bot.handlers import chat
    dp.include_router(chat.router)

    scheduler = setup_scheduler(bot)
    scheduler.start()

    logging.info("Бот запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())