from aiogram import Router, F
from aiogram.types import Message
from database.db import AsyncSessionLocal
from database.models import TestResult
from sqlalchemy import select
from bot.keyboards.test_kb import get_main_keyboard
import logging
from bot.services.insights import get_correlation_insights

router = Router()


@router.message(F.text == "📊 Моя история")
async def show_history(message: Message):
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
                "📭 У тебя пока нет результатов.\n\nПройди первый тест!",
                reply_markup=get_main_keyboard()
            )
            return

        text = "📊 <b>Твои последние результаты:</b>\n\n"
        for r in results:
            date = r.created_at.strftime("%d.%m.%Y")
            text += f"📅 {date} | {r.test_name} | {r.score} баллов | {r.level}\n"

        await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard())

    except Exception as e:
        logging.error(f"History error: {e}")
        await message.answer(f"Ошибка: {str(e)}", reply_markup=get_main_keyboard())



@router.message(F.text == "🔍 Инсайты")
async def show_insights(message: Message):
    insights = await get_correlation_insights(message.from_user.id)

    if not insights:
        await message.answer(
            "📊 Пока недостаточно данных для анализа.\n\n"
            "Делай чек-ин каждый день — через 5-7 дней появятся персональные инсайты!",
            reply_markup=get_main_keyboard()
        )
        return

    await message.answer(
        f"🔍 <b>Персональные инсайты</b>\n\n"
        f"На основе твоих данных за последние 30 дней:\n\n"
        f"{insights}",
        parse_mode="HTML",
        reply_markup=get_main_keyboard()
    )