from aiogram import Router
from aiogram.types import Message
from aiogram.filters import CommandStart, Command
from database.db import AsyncSessionLocal
from database.models import User
from sqlalchemy import select
from bot.keyboards.test_kb import get_main_keyboard

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()

        if not user:
            new_user = User(
                telegram_id=message.from_user.id,
                username=message.from_user.username
            )
            session.add(new_user)
            await session.commit()

    await message.answer(
        f"👋 Привет, {message.from_user.first_name}!\n\n"
        "Я помогу тебе отслеживать своё психологическое состояние.\n\n"
        "⚠️ <b>Важно:</b> Этот бот не является медицинским инструментом "
        "и не заменяет консультацию специалиста.\n\n"
        "Выбери действие:",
        reply_markup=get_main_keyboard(),
        parse_mode="HTML"
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "📌 <b>Что я умею:</b>\n\n"
        "🧪 <b>Пройти тест</b> — PHQ-9 или GAD-7\n"
        "📊 <b>Моя история</b> — результаты прошлых тестов\n"
        "✅ <b>Чек-ин</b> — ежедневная оценка состояния\n\n"
        "⚠️ Бот не ставит диагнозы и не заменяет врача.",
        parse_mode="HTML",
        reply_markup=get_main_keyboard()
    )