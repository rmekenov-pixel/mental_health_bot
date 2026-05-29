from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from bot.states.test_states import CheckInStates
from bot.keyboards.test_kb import get_main_keyboard
from database.db import AsyncSessionLocal
from database.models import CheckIn, UserStreak
from sqlalchemy import select, func
from datetime import datetime, timedelta

router = Router()


@router.message(F.text == "✅ Чек-ин")
async def start_checkin(message: Message, state: FSMContext):
    await state.clear()
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

        # Обновляем streak
        result = await session.execute(
            select(UserStreak).where(UserStreak.telegram_id == message.from_user.id)
        )
        streak = result.scalar_one_or_none()
        today = datetime.utcnow().date()

        if not streak:
            streak = UserStreak(
                telegram_id=message.from_user.id,
                current_streak=1,
                longest_streak=1,
                last_checkin_date=datetime.utcnow()
            )
            session.add(streak)
        else:
            if streak.last_checkin_date:
                last_date = streak.last_checkin_date.date()
                if last_date == today - timedelta(days=1):
                    streak.current_streak += 1
                elif last_date < today - timedelta(days=1):
                    streak.current_streak = 1
            else:
                streak.current_streak = 1

            if streak.current_streak > streak.longest_streak:
                streak.longest_streak = streak.current_streak
            streak.last_checkin_date = datetime.utcnow()

        await session.commit()

    streak_text = ""
    if streak.current_streak >= 3:
        streak_text = f"\n\n🔥 <b>Streak: {streak.current_streak} дней подряд!</b>"
    if streak.current_streak == 7:
        streak_text = f"\n\n🏅 <b>Milestone: Неделя подряд!</b> Так держать! 🎉"
    if streak.current_streak == 30:
        streak_text = f"\n\n🏆 <b>Milestone: Месяц подряд!</b> Ты невероятен! 🎊"
    elif streak.current_streak > 7:
        streak_text = f"\n\n🔥 <b>Streak: {streak.current_streak} дней подряд!</b>"

    # Milestone по общему количеству чек-инов
    async with AsyncSessionLocal() as session:
        total_checkins = await session.execute(
            select(func.count(CheckIn.id)).where(CheckIn.telegram_id == message.from_user.id)
        )
        total = total_checkins.scalar()

    if total == 1:
        streak_text += f"\n\n🎯 <b>Первый чек-ин!</b> Отличное начало!"
    elif total == 10:
        streak_text += f"\n\n⭐ <b>10 чек-инов!</b> Ты формируешь привычку!"
    elif total == 50:
        streak_text += f"\n\n💎 <b>50 чек-инов!</b> Это уже серьёзно!"
    elif total == 100:
        streak_text += f"\n\n👑 <b>100 чек-инов!</b> Легенда заботы о себе!"

    await message.answer(
        f"✅ <b>Чек-ин сохранён!</b>\n\n"
        f"😊 Настроение: <b>{data['mood']}/10</b>\n"
        f"😰 Тревога: <b>{data['anxiety']}/10</b>\n"
        f"⚡ Энергия: <b>{data['energy']}/10</b>\n"
        f"😴 Сон: <b>{data['sleep_hours']} ч. / качество {quality}/10</b>"
        f"{streak_text}\n\n"
        f"Продолжай отслеживать своё состояние каждый день!",
        parse_mode="HTML",
        reply_markup=get_main_keyboard()
    )