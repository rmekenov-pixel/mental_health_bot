import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from aiogram import Bot
from database.db import AsyncSessionLocal
from database.models import User, CheckIn
from sqlalchemy import select
from datetime import datetime, timedelta


async def send_checkin_reminder(bot: Bot):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User))
        users = result.scalars().all()

    for user in users:
        try:
            async with AsyncSessionLocal() as session:
                today = datetime.utcnow().date()
                result = await session.execute(
                    select(CheckIn)
                    .where(CheckIn.telegram_id == user.telegram_id)
                    .where(CheckIn.created_at >= datetime.combine(today, datetime.min.time()))
                )
                checkin_today = result.scalar_one_or_none()

            if not checkin_today:
                await bot.send_message(
                    user.telegram_id,
                    "🔔 <b>Вечерний чек-ин</b>\n\n"
                    "Как прошёл твой день? Не забудь отметить своё состояние!\n\n"
                    "Нажми ✅ Чек-ин",
                    parse_mode="HTML"
                )
        except Exception as e:
            logging.error(f"Reminder error for {user.telegram_id}: {e}")


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()

    # Каждый день в 20:00 по Астане (UTC+5 = 15:00 UTC)
    scheduler.add_job(
        send_checkin_reminder,
        CronTrigger(hour=15, minute=0),
        args=[bot]
    )

    return scheduler