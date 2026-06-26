from aiogram import Router, F
from aiogram.types import Message
from database.db import AsyncSessionLocal
from database.models import CheckIn
from sqlalchemy import select
from datetime import datetime, timedelta
from bot.keyboards.test_kb import get_main_keyboard
from bot.services.localization import t, get_user_lang

router = Router()


@router.message(F.text.in_({t(lang, "btn_calendar") for lang in ("ru", "kz", "en")}))
async def show_calendar(message: Message):
    lang = await get_user_lang(message.from_user.id)
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
            t(lang, "no_calendar"),
            reply_markup=get_main_keyboard(lang)
        )
        return

    checkin_by_date = {}
    for c in checkins:
        date = c.created_at.date()
        checkin_by_date[date] = c.mood

    today = datetime.utcnow().date()
    calendar_text = t(lang, "calendar_title")
    calendar_text += t(lang, "calendar_legend")

    calendar_text += t(lang, "calendar_weekdays") + "\n"

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

    calendar_text += t(lang, "calendar_stats", total=total, good=good, medium=medium, bad=bad)

    await message.answer(f"<pre>{calendar_text}</pre>", parse_mode="HTML", reply_markup=get_main_keyboard(lang))
