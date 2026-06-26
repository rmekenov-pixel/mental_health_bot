from database.db import AsyncSessionLocal
from database.models import CheckIn, TestResult
from sqlalchemy import select
from datetime import datetime, timedelta
from bot.services.localization import t

_LANG_NAMES = {
    "ru": "русском",
    "kz": "казахском",
    "en": "English",
}


async def get_correlation_insights(telegram_id: int, lang: str = "ru") -> str:
    async with AsyncSessionLocal() as session:
        month_ago = datetime.utcnow() - timedelta(days=30)
        result = await session.execute(
            select(CheckIn)
            .where(CheckIn.telegram_id == telegram_id)
            .where(CheckIn.created_at >= month_ago)
            .order_by(CheckIn.created_at)
        )
        checkins = result.scalars().all()

        test_result = await session.execute(
            select(TestResult)
            .where(TestResult.telegram_id == telegram_id)
            .order_by(TestResult.created_at.desc())
            .limit(5)
        )
        tests = test_result.scalars().all()

    if len(checkins) < 3:
        return None

    # Базовая статистика
    avg_mood = sum(c.mood for c in checkins) / len(checkins)
    avg_anxiety = sum(c.anxiety for c in checkins) / len(checkins)
    avg_energy = sum(c.energy for c in checkins) / len(checkins)
    sleep_checkins = [c for c in checkins if c.sleep_hours]
    avg_sleep = sum(c.sleep_hours for c in sleep_checkins) / len(sleep_checkins) if sleep_checkins else None

    # Тренд настроения
    mood_trend = ""
    if len(checkins) >= 5:
        recent = checkins[-3:]
        older = checkins[:-3]
        avg_recent = sum(c.mood for c in recent) / len(recent)
        avg_older = sum(c.mood for c in older) / len(older)
        diff = avg_recent - avg_older
        if diff > 0.5:
            mood_trend = t(lang, "insights_mood_improved", diff=f"{diff:.1f}")
        elif diff < -0.5:
            mood_trend = t(lang, "insights_mood_declined", diff=f"{abs(diff):.1f}")
        else:
            mood_trend = t(lang, "insights_mood_stable")

    # Корреляции сна
    sleep_insight = ""
    if sleep_checkins and len(sleep_checkins) >= 3:
        bad_sleep = [c for c in sleep_checkins if c.sleep_hours < 6]
        good_sleep = [c for c in sleep_checkins if c.sleep_hours >= 7]
        if bad_sleep and good_sleep:
            avg_anxiety_bad = sum(c.anxiety for c in bad_sleep) / len(bad_sleep)
            avg_anxiety_good = sum(c.anxiety for c in good_sleep) / len(good_sleep)
            diff = avg_anxiety_bad - avg_anxiety_good
            if diff > 0.5:
                sleep_insight = t(lang, "insights_sleep_anxiety_link", diff=f"{diff:.1f}")

    # Последние тесты
    test_summary = ""
    if tests:
        test_summary = ", ".join(f"{tr.test_name}: {tr.score} ({tr.level})" for tr in tests[:3])

    # Передаём всё в AI для развёрнутого анализа
    from bot.config import GROQ_API_KEY
    import aiohttp

    if not GROQ_API_KEY:
        return _build_basic_insights(avg_mood, avg_anxiety, avg_energy, avg_sleep, mood_trend, sleep_insight, lang)

    lang_name = _LANG_NAMES.get(lang, _LANG_NAMES["ru"])

    prompt = f"""Проанализируй психологическое состояние пользователя за последние {len(checkins)} дней.

Данные чек-инов:
- Среднее настроение: {avg_mood:.1f}/10
- Средняя тревога: {avg_anxiety:.1f}/10
- Средняя энергия: {avg_energy:.1f}/10
{f'- Средний сон: {avg_sleep:.1f} ч.' if avg_sleep else ''}
{f'- Тренд настроения: {mood_trend}' if mood_trend else ''}
{f'- Связь сна и тревоги: {sleep_insight}' if sleep_insight else ''}
{f'- Последние тесты: {test_summary}' if test_summary else ''}

Напиши персональный анализ (5-7 предложений):
1. Общая картина состояния
2. Что бросается в глаза (паттерны, тренды)
3. Связи между показателями если есть
4. 2-3 конкретные рекомендации основанные на данных
5. Одно ободряющее слово

Пиши тепло, конкретно, без медицинских терминов. На {lang_name} языке."""

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": "Ты заботливый аналитик психологического состояния. Анализируй данные и давай конкретные персональные советы."},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 500,
        "temperature": 0.7
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    return data["choices"][0]["message"]["content"]
    except Exception:
        pass

    return _build_basic_insights(avg_mood, avg_anxiety, avg_energy, avg_sleep, mood_trend, sleep_insight, lang)


def _build_basic_insights(avg_mood, avg_anxiety, avg_energy, avg_sleep, mood_trend, sleep_insight, lang: str = "ru"):
    lines = []
    lines.append(t(lang, "insights_basic_mood", avg_mood=f"{avg_mood:.1f}"))
    lines.append(t(lang, "insights_basic_anxiety", avg_anxiety=f"{avg_anxiety:.1f}"))
    lines.append(t(lang, "insights_basic_energy", avg_energy=f"{avg_energy:.1f}"))
    if avg_sleep:
        lines.append(t(lang, "insights_basic_sleep", avg_sleep=f"{avg_sleep:.1f}"))
    if mood_trend:
        lines.append(t(lang, "insights_basic_mood_trend", trend=mood_trend))
    if sleep_insight:
        lines.append(f"🔗 {sleep_insight}")
    return "\n".join(f"• {l}" for l in lines)
