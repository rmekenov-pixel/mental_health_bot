from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from bot.states.test_states import CheckInStates
from bot.keyboards.test_kb import get_main_keyboard
from database.db import AsyncSessionLocal
from database.models import CheckIn

router = Router()


@router.message(F.text == "✅ Чек-ин")
async def start_checkin(message: Message, state: FSMContext):
    await state.set_state(CheckInStates.mood)
    await message.answer(
        "✅ <b>Ежедневный чек-ин</b>\n\n"
        "Оцени своё состояние прямо сейчас.\n\n"
        "😊 Как твоё <b>настроение</b> сегодня?\n"
        "Введи цифру от 1 до 10\n"
        "(1 — очень плохо, 10 — отлично)",
        parse_mode="HTML"
    )


@router.message(CheckInStates.mood)
async def checkin_mood(message: Message, state: FSMContext):
    try:
        mood = int(message.text)
        if not 1 <= mood <= 10:
            raise ValueError
    except ValueError:
        await message.answer("Пожалуйста, введи цифру от 1 до 10.")
        return

    await state.update_data(mood=mood)
    await state.set_state(CheckInStates.anxiety)
    await message.answer(
        "😰 Как твой уровень <b>тревоги</b>?\n"
        "Введи цифру от 1 до 10\n"
        "(1 — совсем нет тревоги, 10 — очень сильная)",
        parse_mode="HTML"
    )


@router.message(CheckInStates.anxiety)
async def checkin_anxiety(message: Message, state: FSMContext):
    try:
        anxiety = int(message.text)
        if not 1 <= anxiety <= 10:
            raise ValueError
    except ValueError:
        await message.answer("Пожалуйста, введи цифру от 1 до 10.")
        return

    await state.update_data(anxiety=anxiety)
    await state.set_state(CheckInStates.energy)
    await message.answer(
        "⚡ Какой у тебя уровень <b>энергии</b>?\n"
        "Введи цифру от 1 до 10\n"
        "(1 — совсем нет сил, 10 — полон энергии)",
        parse_mode="HTML"
    )


@router.message(CheckInStates.energy)
async def checkin_energy(message: Message, state: FSMContext):
    try:
        energy = int(message.text)
        if not 1 <= energy <= 10:
            raise ValueError
    except ValueError:
        await message.answer("Пожалуйста, введи цифру от 1 до 10.")
        return

    await state.update_data(energy=energy)
    await state.set_state(CheckInStates.sleep_hours)
    await message.answer(
        "😴 Сколько часов ты <b>спал</b> прошлой ночью?\n"
        "Введи цифру от 1 до 12",
        parse_mode="HTML"
    )


@router.message(CheckInStates.sleep_hours)
async def checkin_sleep_hours(message: Message, state: FSMContext):
    try:
        hours = int(message.text)
        if not 1 <= hours <= 12:
            raise ValueError
    except ValueError:
        await message.answer("Пожалуйста, введи цифру от 1 до 12.")
        return

    await state.update_data(sleep_hours=hours)
    await state.set_state(CheckInStates.sleep_quality)
    await message.answer(
        "🌙 Как ты оцениваешь <b>качество сна</b>?\n"
        "Введи цифру от 1 до 10\n"
        "(1 — очень плохо, 10 — отлично)",
        parse_mode="HTML"
    )


@router.message(CheckInStates.sleep_quality)
async def checkin_sleep_quality(message: Message, state: FSMContext):
    try:
        quality = int(message.text)
        if not 1 <= quality <= 10:
            raise ValueError
    except ValueError:
        await message.answer("Пожалуйста, введи цифру от 1 до 10.")
        return

    data = await state.get_data()
    await state.clear()

    async with AsyncSessionLocal() as session:
        checkin = CheckIn(
            telegram_id=message.from_user.id,
            mood=data["mood"],
            anxiety=data["anxiety"],
            energy=data["energy"],
            sleep_hours=data["sleep_hours"],
            sleep_quality=quality
        )
        session.add(checkin)
        await session.commit()

    await message.answer(
        f"✅ <b>Чек-ин сохранён!</b>\n\n"
        f"😊 Настроение: <b>{data['mood']}/10</b>\n"
        f"😰 Тревога: <b>{data['anxiety']}/10</b>\n"
        f"⚡ Энергия: <b>{data['energy']}/10</b>\n"
        f"😴 Сон: <b>{data['sleep_hours']} ч. / качество {quality}/10</b>\n\n"
        f"Продолжай отслеживать своё состояние каждый день!",
        parse_mode="HTML",
        reply_markup=get_main_keyboard()
    )