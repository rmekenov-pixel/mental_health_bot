from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from bot.states.test_states import CheckInStates
from bot.keyboards.test_kb import get_main_keyboard
from bot.services.localization import t, get_user_lang
from database.db import AsyncSessionLocal
from database.models import CheckIn, UserStreak
from sqlalchemy import select, func
from datetime import datetime, timedelta

router = Router()


@router.message(F.text.in_({t(lang, "btn_checkin") for lang in ("ru", "kz", "en")}))
async def start_checkin(message: Message, state: FSMContext):
    lang = await get_user_lang(message.from_user.id)
    await state.clear()
    await state.set_state(CheckInStates.mood)
    await message.answer(
        t(lang, "checkin_start"),
        parse_mode="HTML"
    )


@router.message(CheckInStates.mood)
async def checkin_mood(message: Message, state: FSMContext):
    lang = await get_user_lang(message.from_user.id)
    try:
        mood = int(message.text)
        if not 1 <= mood <= 10:
            raise ValueError
    except ValueError:
        await message.answer(t(lang, "checkin_invalid"))
        return

    await state.update_data(mood=mood)
    await state.set_state(CheckInStates.anxiety)
    await message.answer(
        t(lang, "checkin_anxiety"),
        parse_mode="HTML"
    )


@router.message(CheckInStates.anxiety)
async def checkin_anxiety(message: Message, state: FSMContext):
    lang = await get_user_lang(message.from_user.id)
    try:
        anxiety = int(message.text)
        if not 1 <= anxiety <= 10:
            raise ValueError
    except ValueError:
        await message.answer(t(lang, "checkin_invalid"))
        return

    await state.update_data(anxiety=anxiety)
    await state.set_state(CheckInStates.energy)
    await message.answer(
        t(lang, "checkin_energy"),
        parse_mode="HTML"
    )


@router.message(CheckInStates.energy)
async def checkin_energy(message: Message, state: FSMContext):
    lang = await get_user_lang(message.from_user.id)
    try:
        energy = int(message.text)
        if not 1 <= energy <= 10:
            raise ValueError
    except ValueError:
        await message.answer(t(lang, "checkin_invalid"))
        return

    await state.update_data(energy=energy)
    await state.set_state(CheckInStates.sleep_hours)
    await message.answer(
        t(lang, "checkin_sleep_hours"),
        parse_mode="HTML"
    )


@router.message(CheckInStates.sleep_hours)
async def checkin_sleep_hours(message: Message, state: FSMContext):
    lang = await get_user_lang(message.from_user.id)
    try:
        hours = int(message.text)
        if not 1 <= hours <= 12:
            raise ValueError
    except ValueError:
        await message.answer(t(lang, "checkin_invalid"))
        return

    await state.update_data(sleep_hours=hours)
    await state.set_state(CheckInStates.sleep_quality)
    await message.answer(
        t(lang, "checkin_sleep_quality"),
        parse_mode="HTML"
    )


@router.message(CheckInStates.sleep_quality)
async def checkin_sleep_quality(message: Message, state: FSMContext):
    lang = await get_user_lang(message.from_user.id)
    try:
        quality = int(message.text)
        if not 1 <= quality <= 10:
            raise ValueError
    except ValueError:
        await message.answer(t(lang, "checkin_invalid"))
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
        streak_text = t(lang, "checkin_streak", days=streak.current_streak)
    if streak.current_streak == 7:
        streak_text = t(lang, "checkin_milestone_week")
    if streak.current_streak == 30:
        streak_text = t(lang, "checkin_milestone_month")
    elif streak.current_streak > 7:
        streak_text = t(lang, "checkin_streak", days=streak.current_streak)

    # Milestone по общему количеству чек-инов
    async with AsyncSessionLocal() as session:
        total_checkins = await session.execute(
            select(func.count(CheckIn.id)).where(CheckIn.telegram_id == message.from_user.id)
        )
        total = total_checkins.scalar()

    if total == 1:
        streak_text += t(lang, "checkin_milestone_first")
    elif total == 10:
        streak_text += t(lang, "checkin_milestone_10")
    elif total == 50:
        streak_text += t(lang, "checkin_milestone_50")
    elif total == 100:
        streak_text += t(lang, "checkin_milestone_100")

    done_text = t(
        lang, "checkin_done",
        mood=data["mood"], anxiety=data["anxiety"], energy=data["energy"],
        sleep_hours=data["sleep_hours"], sleep_quality=quality
    )
    done_text += streak_text + t(lang, "checkin_done_footer")

    await message.answer(
        done_text,
        parse_mode="HTML",
        reply_markup=get_main_keyboard(lang)
    )
