from database.db import AsyncSessionLocal
from database.models import CheckIn
from sqlalchemy import select
from datetime import datetime, timedelta


async def get_correlation_insights(telegram_id: int) -> str:
    async with AsyncSessionLocal() as session:
        month_ago = datetime.utcnow() - timedelta(days=30)
        result = await session.execute(
            select(CheckIn)
            .where(CheckIn.telegram_id == telegram_id)
            .where(CheckIn.created_at >= month_ago)
            .order_by(CheckIn.created_at)
        )
        checkins = result.scalars().all()

    if len(checkins) < 5:
        return None

    insights = []

    # Связь сна и тревоги
    sleep_checkins = [c for c in checkins if c.sleep_hours]
    if len(sleep_checkins) >= 5:
        bad_sleep = [c for c in sleep_checkins if c.sleep_hours < 6]
        good_sleep = [c for c in sleep_checkins if c.sleep_hours >= 7]

        if bad_sleep and good_sleep:
            avg_anxiety_bad = sum(c.anxiety for c in bad_sleep) / len(bad_sleep)
            avg_anxiety_good = sum(c.anxiety for c in good_sleep) / len(good_sleep)
            diff = avg_anxiety_bad - avg_anxiety_good
            if diff > 1:
                insights.append(
                    f"😴 При коротком сне (<6ч) твоя тревога выше на <b>{diff:.1f} балла</b>"
                )

    # Связь сна и настроения
    if len(sleep_checkins) >= 5:
        bad_sleep = [c for c in sleep_checkins if c.sleep_hours < 6]
        good_sleep = [c for c in sleep_checkins if c.sleep_hours >= 7]

        if bad_sleep and good_sleep:
            avg_mood_bad = sum(c.mood for c in bad_sleep) / len(bad_sleep)
            avg_mood_good = sum(c.mood for c in good_sleep) / len(good_sleep)
            diff = avg_mood_good - avg_mood_bad
            if diff > 1:
                insights.append(
                    f"😊 При хорошем сне (7+ч) настроение выше на <b>{diff:.1f} балла</b>"
                )

    # Связь энергии и настроения
    high_energy = [c for c in checkins if c.energy >= 7]
    low_energy = [c for c in checkins if c.energy <= 4]

    if high_energy and low_energy:
        avg_mood_high = sum(c.mood for c in high_energy) / len(high_energy)
        avg_mood_low = sum(c.mood for c in low_energy) / len(low_energy)
        diff = avg_mood_high - avg_mood_low
        if diff > 1:
            insights.append(
                f"⚡ В дни с высокой энергией настроение выше на <b>{diff:.1f} балла</b>"
            )

    # Тренд настроения
    if len(checkins) >= 7:
        recent = checkins[-7:]
        older = checkins[:-7]
        if older:
            avg_recent = sum(c.mood for c in recent) / len(recent)
            avg_older = sum(c.mood for c in older) / len(older)
            diff = avg_recent - avg_older
            if diff > 0.5:
                insights.append(f"📈 Твоё настроение улучшилось за последнюю неделю на <b>{diff:.1f} балла</b>")
            elif diff < -0.5:
                insights.append(f"📉 Твоё настроение снизилось за последнюю неделю на <b>{abs(diff):.1f} балла</b>")

    if not insights:
        return None

    return "\n".join(f"• {i}" for i in insights)