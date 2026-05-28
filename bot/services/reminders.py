import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from aiogram import Bot
from database.db import AsyncSessionLocal
from database.models import User, CheckIn, TestResult
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


async def send_weekly_report(bot: Bot):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User))
        users = result.scalars().all()

    for user in users:
        try:
            async with AsyncSessionLocal() as session:
                week_ago = datetime.utcnow() - timedelta(days=7)

                checkin_result = await session.execute(
                    select(CheckIn)
                    .where(CheckIn.telegram_id == user.telegram_id)
                    .where(CheckIn.created_at >= week_ago)
                )
                checkins = checkin_result.scalars().all()

                test_result = await session.execute(
                    select(TestResult)
                    .where(TestResult.telegram_id == user.telegram_id)
                    .where(TestResult.created_at >= week_ago)
                )
                tests = test_result.scalars().all()

            if not checkins and not tests:
                continue

            text = "📊 <b>Итоги недели</b>\n\n"

            if checkins:
                avg_mood = sum(c.mood for c in checkins) / len(checkins)
                avg_anxiety = sum(c.anxiety for c in checkins) / len(checkins)
                avg_energy = sum(c.energy for c in checkins) / len(checkins)
                sleep_checkins = [c for c in checkins if c.sleep_hours]
                avg_sleep = sum(c.sleep_hours for c in sleep_checkins) / len(sleep_checkins) if sleep_checkins else 0

                text += f"✅ Чек-инов за неделю: <b>{len(checkins)}</b>\n\n"
                text += f"😊 Среднее настроение: <b>{avg_mood:.1f}/10</b>\n"
                text += f"😰 Средняя тревога: <b>{avg_anxiety:.1f}/10</b>\n"
                text += f"⚡ Средняя энергия: <b>{avg_energy:.1f}/10</b>\n"
                if avg_sleep:
                    text += f"😴 Средний сон: <b>{avg_sleep:.1f} ч.</b>\n"

            if tests:
                text += f"\n🧪 Тестов пройдено: <b>{len(tests)}</b>\n"
                for t in tests:
                    text += f"• {t.test_name}: {t.score} баллов — {t.level}\n"

            text += "\nПродолжай отслеживать своё состояние! 💪"

            await bot.send_message(user.telegram_id, text, parse_mode="HTML")

            # AI анализ недели
            if checkins:
                from bot.services.ai_explanation import get_ai_weekly_reflection
                reflection = await get_ai_weekly_reflection(
                    avg_mood=avg_mood,
                    avg_anxiety=avg_anxiety,
                    avg_energy=avg_energy,
                    checkin_count=len(checkins)
                )
                await bot.send_message(
                    user.telegram_id,
                    f"🧠 <b>AI-анализ твоей недели:</b>\n\n{reflection}",
                    parse_mode="HTML"
                )

        except Exception as e:
            logging.error(f"Weekly report error for {user.telegram_id}: {e}")


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()

    # Каждый день в 20:00 по Астане (UTC+5 = 15:00 UTC)
    scheduler.add_job(
        send_checkin_reminder,
        CronTrigger(hour=15, minute=0),
        args=[bot]
    )

    # Каждое воскресенье в 19:00 по Астане (UTC+5 = 14:00 UTC)
    scheduler.add_job(
        send_weekly_report,
        CronTrigger(day_of_week="sun", hour=14, minute=0),
        args=[bot]
    )

    return scheduler