from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database.db import AsyncSessionLocal
from database.models import Feedback
from bot.keyboards.test_kb import get_main_keyboard

router = Router()


class FeedbackStates(StatesGroup):
    waiting_comment = State()


def get_feedback_keyboard() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👍 Полезно", callback_data="feedback_positive"),
            InlineKeyboardButton(text="👎 Не полезно", callback_data="feedback_negative"),
        ]
    ])
    return keyboard


@router.message(F.text == "💬 Обратная связь")
async def ask_feedback(message: Message):
    await message.answer(
        "💬 <b>Обратная связь</b>\n\n"
        "Насколько полезен для тебя этот бот?",
        parse_mode="HTML",
        reply_markup=get_feedback_keyboard()
    )


@router.callback_query(F.data == "feedback_positive")
async def feedback_positive(callback: CallbackQuery):
    async with AsyncSessionLocal() as session:
        feedback = Feedback(
            telegram_id=callback.from_user.id,
            rating="positive"
        )
        session.add(feedback)
        await session.commit()

    await callback.message.edit_text(
        "👍 Спасибо за отзыв! Рады что помогаем 🙏"
    )
    await callback.answer()


@router.callback_query(F.data == "feedback_negative")
async def feedback_negative(callback: CallbackQuery, state: FSMContext):
    await state.set_state(FeedbackStates.waiting_comment)
    await callback.message.edit_text(
        "👎 Жаль это слышать. Напиши что можно улучшить:"
    )
    await callback.answer()


@router.message(FeedbackStates.waiting_comment)
async def save_feedback_comment(message: Message, state: FSMContext):
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
        "🙏 Спасибо за честный отзыв! Мы обязательно учтём это.",
        reply_markup=get_main_keyboard()
    )