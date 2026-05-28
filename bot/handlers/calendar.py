from aiogram import Router, F
from aiogram.types import Message
from database.db import AsyncSessionLocal
from database.models import CheckIn
from sqlalchemy import select
from datetime import datetime, timedelta
from bot.keyboards.test_kb import get_main_keyboard

router = Router()


@router.message(F.text == "📅 Календарь")
async def show_calendar(message: Message):
    async with AsyncSessionLocal() as session:
        month_ago = datetime.utcnow() - timedelta(days=30)
        result = await session.execute(
            select(CheckIn)
            .where(CheckIn.telegram_id == message.from_user.id)
            .where(CheckIn.created_at >= month_ago)
            .order_by(CheckIn.created_at)
        )
        checkins = result.scalars().all()

    if not checkins:
        await message.answer(
            "📅 Пока нет данных для календаря.\n\n"
            "Делай чек-ин каждый день — и увидишь свой эмоциональный календарь!",
            reply_markup=get_main_keyboard()
        )
        return

    checkin_by_date = {}
    for c in checkins:
        date = c.created_at.date()
        checkin_by_date[date] = c.mood

    today = datetime.utcnow().date()
    calendar_text = "📅 <b>Эмоциональный календарь (30 дней)</b>\n\n"
    calendar_text += "🟩 хорошо (7-10)  🟨 средне (4-6)  🟥 тяжело (1-3)\n\n"

    week_days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    calendar_text += " ".join(week_days) + "\n"

    start_date = today - timedelta(days=29)
    first_weekday = start_date.weekday()

    row = ["  "] * first_weekday
    for i in range(30):
        date = start_date + timedelta(days=i)
        mood = checkin_by_date.get(date)

        if mood is None:
            emoji = "⬜"
        elif mood >= 7:
            emoji = "🟩"
        elif mood >= 4:
            emoji = "🟨"
        else:
            emoji = "🟥"

        row.append(emoji)

        if len(row) == 7:
            calendar_text += " ".join(row) + "\n"
            row = []

    if row:
        row += ["  "] * (7 - len(row))
        calendar_text += " ".join(row) + "\n"

    total = len(checkin_by_date)
    good = sum(1 for m in checkin_by_date.values() if m >= 7)
    medium = sum(1 for m in checkin_by_date.values() if 4 <= m < 7)
    bad = sum(1 for m in checkin_by_date.values() if m < 4)

    calendar_text += f"\n📊 За 30 дней: {total} чек-инов\n"
    calendar_text += f"🟩 Хороших: {good} | 🟨 Средних: {medium} | 🟥 Тяжёлых: {bad}"

    await message.answer(f"<pre>{calendar_text}</pre>", parse_mode="HTML", reply_markup=get_main_keyboard())