import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from bot.config import BOT_TOKEN
from bot.handlers import start, tests, history, checkin, charts, feedback, admin
from bot.services.reminders import setup_scheduler
from database.db import init_db

logging.basicConfig(level=logging.INFO)


async def main():
    await init_db()

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    dp.include_router(start.router)
    dp.include_router(tests.router)
    dp.include_router(history.router)
    dp.include_router(checkin.router)
    dp.include_router(charts.router)
    dp.include_router(feedback.router)
    dp.include_router(admin.router)

    scheduler = setup_scheduler(bot)
    scheduler.start()

    logging.info("Бот запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())