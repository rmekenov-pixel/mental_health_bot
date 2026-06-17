import asyncio
import logging
from aiogram import Bot, Dispatcher, BaseMiddleware
from aiogram.types import TelegramObject
from aiogram.fsm.storage.memory import MemoryStorage
from bot.config import BOT_TOKEN
from bot.handlers import start, tests, history, checkin, charts, feedback, admin, calendar, language
from bot.services.reminders import setup_scheduler
from database.db import init_db
from typing import Callable, Dict, Any, Awaitable

logging.basicConfig(level=logging.INFO)

MAIN_MENU_BUTTONS = [
    "🧪 Пройти тест", "📊 Моя история", "✅ Чек-ин",
    "📈 График", "🔍 Инсайты", "📅 Календарь", "💬 Обратная связь"
]


class ResetStateMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        state = data.get("state")
        if state and hasattr(event, 'text') and event.text:
            if event.text in MAIN_MENU_BUTTONS:
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

    scheduler = setup_scheduler(bot)
    scheduler.start()

    logging.info("Бот запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())