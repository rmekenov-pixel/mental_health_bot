from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from database.db import AsyncSessionLocal
from database.models import User, TestResult, CheckIn, Feedback
from sqlalchemy import select, func
from datetime import datetime, timedelta

router = Router()

ADMIN_ID = 342498582


@router.message(Command("admin"))
async def admin_panel(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    async with AsyncSessionLocal() as session:
        # Всего пользователей
        total_users = await session.execute(select(func.count(User.id)))
        total_users = total_users.scalar()

        # Новых за 7 дней
        week_ago = datetime.utcnow() - timedelta(days=7)
        new_users = await session.execute(
            select(func.count(User.id)).where(User.created_at >= week_ago)
        )
        new_users = new_users.scalar()

        # Всего тестов
        total_tests = await session.execute(select(func.count(TestResult.id)))
        total_tests = total_tests.scalar()

        # Тестов за 7 дней
        recent_tests = await session.execute(
            select(func.count(TestResult.id)).where(TestResult.created_at >= week_ago)
        )
        recent_tests = recent_tests.scalar()

        # Всего чек-инов
        total_checkins = await session.execute(select(func.count(CheckIn.id)))
        total_checkins = total_checkins.scalar()

        # Чек-инов за 7 дней
        recent_checkins = await session.execute(
            select(func.count(CheckIn.id)).where(CheckIn.created_at >= week_ago)
        )
        recent_checkins = recent_checkins.scalar()

        # Фидбэк
        positive = await session.execute(
            select(func.count(Feedback.id)).where(Feedback.rating == "positive")
        )
        positive = positive.scalar()

        negative = await session.execute(
            select(func.count(Feedback.id)).where(Feedback.rating == "negative")
        )
        negative = negative.scalar()

        # Популярные тесты
        popular = await session.execute(
            select(TestResult.test_name, func.count(TestResult.id).label("cnt"))
            .group_by(TestResult.test_name)
            .order_by(func.count(TestResult.id).desc())
        )
        popular = popular.all()

    popular_text = ""
    for name, cnt in popular:
        popular_text += f"  • {name}: {cnt}\n"

    await message.answer(
        f"📊 <b>Админ-панель MindCheck</b>\n\n"
        f"👥 <b>Пользователи:</b>\n"
        f"  Всего: {total_users}\n"
        f"  Новых за 7 дней: {new_users}\n\n"
        f"🧪 <b>Тесты:</b>\n"
        f"  Всего пройдено: {total_tests}\n"
        f"  За 7 дней: {recent_tests}\n\n"
        f"✅ <b>Чек-ины:</b>\n"
        f"  Всего: {total_checkins}\n"
        f"  За 7 дней: {recent_checkins}\n\n"
        f"💬 <b>Фидбэк:</b>\n"
        f"  👍 Полезно: {positive}\n"
        f"  👎 Не полезно: {negative}\n\n"
        f"🏆 <b>Популярные тесты:</b>\n{popular_text}",
        parse_mode="HTML"
    )