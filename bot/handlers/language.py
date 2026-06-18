from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from database.db import AsyncSessionLocal
from database.models import User
from sqlalchemy import select
from bot.services.localization import t

router = Router()


def get_language_keyboard() -> ReplyKeyboardMarkup:
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🇷🇺 Русский")],
            [KeyboardButton(text="🇰🇿 Қазақша")],
            [KeyboardButton(text="🇬🇧 English")],
        ],
        resize_keyboard=True
    )
    return keyboard


LANG_MAP = {
    "🇷🇺 Русский": "ru",
    "🇰🇿 Қазақша": "kz",
    "🇬🇧 English": "en",
}


@router.message(Command("language"))
async def choose_language(message: Message):
    await message.answer(
        "🌍 Выбери язык / Тілді таңдаңыз / Choose language:",
        reply_markup=get_language_keyboard()
    )


@router.message(F.text.in_(LANG_MAP.keys()))
async def set_language(message: Message, state: FSMContext):
    await state.clear()
    lang = LANG_MAP[message.text]

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()
        is_new_user = False
        if user:
            user.language = lang
            await session.commit()
            is_new_user = user.utc_offset is None
        
    from bot.keyboards.test_kb import get_main_keyboard
    from bot.states.test_states import ReminderStates

    await message.answer(
        t(lang, "start_new" if is_new_user else "start_existing", 
          name=message.from_user.first_name),
        parse_mode="HTML",
        reply_markup=get_main_keyboard()
    )
    
    if is_new_user:
        await message.answer(
            t(lang, "reminder_ask"),
            parse_mode="HTML"
        )
        await state.set_state(ReminderStates.waiting_time)

    from bot.keyboards.test_kb import get_main_keyboard
    await message.answer(
        t(lang, "start_existing", name=message.from_user.first_name),
        parse_mode="HTML",
        reply_markup=get_main_keyboard()
    )