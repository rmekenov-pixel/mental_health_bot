from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from database.db import AsyncSessionLocal
from database.models import User
from sqlalchemy import select
from bot.keyboards.test_kb import get_main_keyboard
from bot.states.test_states import ReminderStates

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()

        if not user:
            new_user = User(
                telegram_id=message.from_user.id,
                username=message.from_user.username,
                reminder_time="20:00"
            )
            session.add(new_user)
            await session.commit()

            await message.answer(
                f"👋 Привет, {message.from_user.first_name}!\n\n"
                f"Большинство людей замечают эмоциональное выгорание слишком поздно.\n\n"
                f"🧠 <b>MindCheck помогает отслеживать:</b>\n"
                f"— тревожность\n"
                f"— стресс\n"
                f"— сон\n"
                f"— настроение\n"
                f"— уровень энергии\n\n"
                f"📊 Чем дольше пользуешься ботом, тем точнее видишь свои эмоциональные паттерны и изменения состояния.\n\n"
                f"🤖 AI поможет понять результаты тестов простым языком.\n\n"
                f"⚠️ Бот не ставит диагнозы и не заменяет специалиста.\n\n"
                f"Начнём с короткого теста 👇",
                parse_mode="HTML",
                reply_markup=get_main_keyboard()
            )
        else:
            await message.answer(
                f"👋 Привет, {message.from_user.first_name}!\n\n"
                "Выбери действие:",
                reply_markup=get_main_keyboard(),
                parse_mode="HTML"
            )


@router.message(ReminderStates.waiting_time)
async def set_reminder_time(message: Message, state: FSMContext):
    time_text = message.text.strip()

    try:
        parts = time_text.split(":")
        if len(parts) != 2:
            raise ValueError
        hour, minute = int(parts[0]), int(parts[1])
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError
    except ValueError:
        await message.answer(
            "❌ Неверный формат. Напиши время в формате ЧЧ:ММ, например: 09:00 или 21:30"
        )
        return

    # Определяем UTC offset автоматически
    from datetime import datetime
    utc_now = datetime.utcnow()
    utc_offset = hour - utc_now.hour
    if utc_offset < -12:
        utc_offset += 24
    elif utc_offset > 14:
        utc_offset -= 24

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()
        if user:
            user.reminder_time = time_text
            user.utc_offset = utc_offset
            await session.commit()

    await state.clear()
    await message.answer(
        f"✅ Буду напоминать о чек-ине в <b>{time_text}</b> каждый день.\n\n"
        f"Выбери действие:",
        parse_mode="HTML",
        reply_markup=get_main_keyboard()
    )


@router.message(Command("reminder"))
async def change_reminder(message: Message, state: FSMContext):
    await state.set_state(ReminderStates.waiting_time)
    await message.answer(
        "🔔 В какое время присылать напоминание?\n"
        "Напиши в формате ЧЧ:ММ, например: <b>09:00</b> или <b>21:30</b>",
        parse_mode="HTML"
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "📌 <b>Что я умею:</b>\n\n"
        "🧪 <b>Пройти тест</b> — PHQ-9, GAD-7, Burnout, Самооценка, EQ\n"
        "📊 <b>Моя история</b> — результаты прошлых тестов\n"
        "✅ <b>Чек-ин</b> — ежедневная оценка состояния\n"
        "📈 <b>График</b> — динамика за 7 дней\n"
        "🔍 <b>Инсайты</b> — персональные корреляции\n"
        "📅 <b>Календарь</b> — эмоциональный календарь за 30 дней\n\n"
        "/reminder — изменить время напоминания\n\n"
        "⚠️ Бот не ставит диагнозы и не заменяет врача.",
        parse_mode="HTML",
        reply_markup=get_main_keyboard()
    )