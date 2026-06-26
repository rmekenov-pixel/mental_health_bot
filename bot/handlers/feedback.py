from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database.db import AsyncSessionLocal
from database.models import Feedback
from bot.keyboards.test_kb import get_main_keyboard
from bot.services.localization import t, get_user_lang

router = Router()


class FeedbackStates(StatesGroup):
    waiting_comment = State()


def get_feedback_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=t(lang, "btn_feedback_positive"), callback_data="feedback_positive"),
            InlineKeyboardButton(text=t(lang, "btn_feedback_negative"), callback_data="feedback_negative"),
        ]
    ])
    return keyboard


@router.message(F.text.in_({t(lang, "btn_feedback") for lang in ("ru", "kz", "en")}))
async def ask_feedback(message: Message):
    lang = await get_user_lang(message.from_user.id)
    await message.answer(
        t(lang, "feedback_ask"),
        parse_mode="HTML",
        reply_markup=get_feedback_keyboard(lang)
    )


@router.callback_query(F.data == "feedback_positive")
async def feedback_positive(callback: CallbackQuery):
    lang = await get_user_lang(callback.from_user.id)
    async with AsyncSessionLocal() as session:
        feedback = Feedback(
            telegram_id=callback.from_user.id,
            rating="positive"
        )
        session.add(feedback)
        await session.commit()

    await callback.message.edit_text(
        t(lang, "feedback_thanks_positive")
    )
    await callback.answer()


@router.callback_query(F.data == "feedback_negative")
async def feedback_negative(callback: CallbackQuery, state: FSMContext):
    lang = await get_user_lang(callback.from_user.id)
    await state.set_state(FeedbackStates.waiting_comment)
    await callback.message.edit_text(
        t(lang, "feedback_ask_comment")
    )
    await callback.answer()


@router.message(FeedbackStates.waiting_comment)
async def save_feedback_comment(message: Message, state: FSMContext):
    lang = await get_user_lang(message.from_user.id)
    async with AsyncSessionLocal() as session:
        feedback = Feedback(
            telegram_id=message.from_user.id,
            rating="negative",
            comment=message.text
        )
        session.add(feedback)
        await session.commit()

    await state.clear()
    await message.answer(
        t(lang, "feedback_thanks_negative"),
        reply_markup=get_main_keyboard(lang)
    )
