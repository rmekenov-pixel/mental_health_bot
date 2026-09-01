from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from database.db import AsyncSessionLocal
from database.models import User
from sqlalchemy import select
from bot.keyboards.test_kb import get_main_keyboard
from bot.states.test_states import ReminderStates
from bot.services.localization import t, get_user_lang
from bot.handlers.language import get_language_keyboard, LANG_MAP
from bot.services.ai_explanation import test_ai_connection

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
                reminder_time="20:00",
                language="ru"
            )
            session.add(new_user)
            await session.commit()

            await message.answer(
                t("ru", "choose_language"),
                reply_markup=get_language_keyboard()
            )
        else:
            lang = user.language or "ru"
            await message.answer(
                t(lang, "start_existing", name=message.from_user.first_name),
                reply_markup=get_main_keyboard(lang),
                parse_mode="HTML"
            )


@router.message(ReminderStates.waiting_time)
async def set_reminder_time(message: Message, state: FSMContext):
    time_text = message.text.strip()
    lang = await get_user_lang(message.from_user.id)

    try:
        parts = time_text.split(":")
        if len(parts) != 2:
            raise ValueError
        hour, minute = int(parts[0]), int(parts[1])
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError
    except ValueError:
        await message.answer(t(lang, "reminder_invalid"))
        return

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
        t(lang, "reminder_set", time=time_text),
        parse_mode="HTML",
        reply_markup=get_main_keyboard(lang)
    )


@router.message(Command("reminder"))
async def change_reminder(message: Message, state: FSMContext):
    lang = await get_user_lang(message.from_user.id)
    await state.set_state(ReminderStates.waiting_time)
    await message.answer(
        t(lang, "reminder_ask"),
        parse_mode="HTML"
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    lang = await get_user_lang(message.from_user.id)
    await message.answer(
        t(lang, "help"),
        parse_mode="HTML",
        reply_markup=get_main_keyboard(lang)
    )


@router.message(Command("ai_status"))
async def cmd_ai_status(message: Message):
    """Диагностическая команда проверки AI подключения."""
    msg = await message.answer("🔄 Проверяю подключение к AI провайдерам...")
    diag = await test_ai_connection()
    
    text = (
        "🔍 <b>Диагностика AI подключения:</b>\n\n"
        f"• <b>Google Gemini API Key:</b> {f'✅ ({diag[\"gemini_key_mask\"]})' if diag['gemini_key_present'] else '❌ Не найден'}\n"
        f"  Статус: {diag['gemini_status']}\n\n"
        f"• <b>Groq API Key:</b> {f'✅ ({diag[\"groq_key_mask\"]})' if diag['groq_key_present'] else '❌ Не найден'}\n"
        f"  Статус: {diag['groq_status']}"
    )
    await msg.edit_text(text, parse_mode="HTML")