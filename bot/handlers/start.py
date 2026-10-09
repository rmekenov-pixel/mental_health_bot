import html
from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from database.db import AsyncSessionLocal
from database.models import User, TestResult, CheckIn, UserStreak, Feedback
from sqlalchemy import select, delete
from bot.keyboards.test_kb import get_main_keyboard
from bot.states.test_states import ReminderStates
from bot.services.localization import t, get_user_lang
from bot.handlers.language import get_language_keyboard, LANG_MAP
from bot.services.ai_explanation import test_ai_connection
from bot.config import ADMIN_ID

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
            safe_name = html.escape(message.from_user.first_name or "")
            await message.answer(
                t(lang, "start_existing", name=safe_name),
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
    """Диагностическая команда проверки AI подключения (только для администратора)."""
    if message.from_user.id != ADMIN_ID:
        return

    msg = await message.answer("🔄 Проверяю подключение к AI провайдерам...")
    diag = await test_ai_connection()

    gemini_key_str = f"✅ ({diag['gemini_key_mask']})" if diag["gemini_key_present"] else "❌ Не найден в контейнере"
    groq_key_str = f"✅ ({diag['groq_key_mask']})" if diag["groq_key_present"] else "❌ Не найден в контейнере"

    text = (
        "🔍 <b>Диагностика AI подключения:</b>\n\n"
        f"• <b>Google Gemini API Key:</b> {gemini_key_str}\n"
        f"  Статус: {diag['gemini_status']}\n\n"
        f"• <b>Groq API Key:</b> {groq_key_str}\n"
        f"  Статус: {diag['groq_status']}\n\n"
        f"📋 <i>Переменные, видимые в контейнере:</i>\n<code>{diag['detected_env_names']}</code>"
    )
    await msg.edit_text(text, parse_mode="HTML")


@router.message(Command("delete_my_data"))
async def cmd_delete_my_data(message: Message):
    """Команда полного удаления данных пользователя (GDPR / Право на забвение)."""
    lang = await get_user_lang(message.from_user.id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🗑 Да, удалить все данные", callback_data="confirm_delete_data"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_delete_data"),
        ]
    ])
    warning_text = (
        "⚠️ <b>Внимание: удаление всех ваших данных</b>\n\n"
        "Это действие безвозвратно удалит:\n"
        "• Всю историю прохождения психологических тестов\n"
        "• Все ежедневные чек-ины и график динамики\n"
        "• Данные стриков и персональные настройки\n\n"
        "Вы уверены, что хотите полностью стереть историю?"
    )
    if lang == "kz":
        warning_text = (
            "⚠️ <b>Назар аударыңыз: барлық деректерді өшіру</b>\n\n"
            "Бұл әрекет сіздің барлық деректеріңізді (тест нәтижелері, чек-индер, күнтізбе және тарих) біржола өшіреді.\n\n"
            "Барлық деректерді өшіруге сенімдісіз бе?"
        )
    elif lang == "en":
        warning_text = (
            "⚠️ <b>Warning: Complete data erasure</b>\n\n"
            "This action will permanently delete:\n"
            "• All test results\n"
            "• All daily check-ins and mood charts\n"
            "• Your streaks and personalized settings\n\n"
            "Are you sure you want to permanently delete your data?"
        )

    await message.answer(warning_text, parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data == "confirm_delete_data")
async def confirm_delete_data(callback: CallbackQuery, state: FSMContext):
    telegram_id = callback.from_user.id
    lang = await get_user_lang(telegram_id)

    await state.clear()
    async with AsyncSessionLocal() as session:
        await session.execute(delete(TestResult).where(TestResult.telegram_id == telegram_id))
        await session.execute(delete(CheckIn).where(CheckIn.telegram_id == telegram_id))
        await session.execute(delete(UserStreak).where(UserStreak.telegram_id == telegram_id))
        await session.execute(delete(Feedback).where(Feedback.telegram_id == telegram_id))
        await session.execute(delete(User).where(User.telegram_id == telegram_id))
        await session.commit()

    done_msg = "🗑 <b>Все ваши данные успешно и безвозвратно удалены.</b>\n\nЧтобы начать заново, отправьте /start."
    if lang == "kz":
        done_msg = "🗑 <b>Барлық деректеріңіз сәтті өшірілді.</b>\n\nҚайта бастау үшін /start жіберіңіз."
    elif lang == "en":
        done_msg = "🗑 <b>All your data has been permanently erased.</b>\n\nSend /start to begin anew."

    await callback.message.edit_text(done_msg, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "cancel_delete_data")
async def cancel_delete_data(callback: CallbackQuery):
    lang = await get_user_lang(callback.from_user.id)
    cancel_msg = "Операция отменена. Ваши данные в безопасности."
    if lang == "kz":
        cancel_msg = "Әрекет тоқтатылды. Деректеріңіз қауіпсіз сақталды."
    elif lang == "en":
        cancel_msg = "Operation cancelled. Your data remains safe."

    await callback.message.edit_text(cancel_msg)
    await callback.answer()