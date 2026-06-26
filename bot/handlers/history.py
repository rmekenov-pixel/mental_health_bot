from aiogram import Router, F
from aiogram.types import Message
from database.db import AsyncSessionLocal
from database.models import TestResult
from sqlalchemy import select
from bot.keyboards.test_kb import get_main_keyboard
from bot.services.localization import t, get_user_lang
import logging
from bot.services.insights import get_correlation_insights

router = Router()


@router.message(F.text.in_({t(lang, "btn_history") for lang in ("ru", "kz", "en")}))
async def show_history(message: Message):
    lang = await get_user_lang(message.from_user.id)
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(TestResult)
                .where(TestResult.telegram_id == message.from_user.id)
                .order_by(TestResult.created_at.desc())
                .limit(10)
            )
            results = result.scalars().all()

        if not results:
            await message.answer(
                t(lang, "no_results"),
                reply_markup=get_main_keyboard(lang)
            )
            return

        text = t(lang, "history_title")
        for r in results:
            date = r.created_at.strftime("%d.%m.%Y")
            text += t(lang, "history_line", date=date, test_name=r.test_name, score=r.score, level=r.level)

        await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard(lang))

    except Exception as e:
        logging.error(f"History error: {e}")
        await message.answer(f"Ошибка: {str(e)}", reply_markup=get_main_keyboard(lang))



@router.message(F.text.in_({t(lang, "btn_insights") for lang in ("ru", "kz", "en")}))
async def show_insights(message: Message):
    lang = await get_user_lang(message.from_user.id)
    insights = await get_correlation_insights(message.from_user.id, lang)

    if not insights:
        await message.answer(
            t(lang, "no_insights"),
            reply_markup=get_main_keyboard(lang)
        )
        return

    await message.answer(
        t(lang, "insights_title") + t(lang, "insights_subtitle") + insights,
        parse_mode="HTML",
        reply_markup=get_main_keyboard(lang)
    )
