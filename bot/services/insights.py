import logging
from database.db import AsyncSessionLocal
from database.models import CheckIn, TestResult
from sqlalchemy import select
from datetime import datetime, timedelta
from bot.services.localization import t
from bot.services.ai_explanation import _call_ai
from bot.config import GROQ_API_KEY, GEMINI_API_KEY

logger = logging.getLogger("insights")

_LANG_NAMES = {
    "ru": "русском",
    "kz": "казахском",
    "en": "English",
}

SYSTEM_PROMPT_INSIGHTS = """Ты помощник по психологическому самонаблюдению. Ты НЕ психолог и НЕ врач.

Твоя задача — анализировать конкретные изменения в показателях и давать точечные рекомендации.

Правила:
- Реагируй только на то что реально изменилось в данных — не комментируй стабильные показатели общими словами
- Каждая рекомендация привязана к конкретному изменению: "сон упал → вот что делать"
- Называй практики по имени и давай инструкцию: не "попробуй медитацию", а "сделай body scan: ляг, закрой глаза, медленно переноси внимание от пальцев ног вверх в течение 10 минут"
- Запрещено: "надейся", "береги себя", "занимайся тем что нравится", любые общие слова без конкретного действия
- Если изменений нет — скажи об этом честно и коротко
- При серьёзных показателях (тревога >8, настроение <3 стабильно) — мягко рекомендуй специалиста"""


async def get_correlation_insights(telegram_id: int, lang: str = "ru") -> str:
    async with AsyncSessionLocal() as session:
        now = datetime.utcnow()
        month_ago = now - timedelta(days=30)
        two_weeks_ago = now - timedelta(days=14)
        one_week_ago = now - timedelta(days=7)

        # Все чекины за месяц
        result = await session.execute(
            select(CheckIn)
            .where(CheckIn.telegram_id == telegram_id)
            .where(CheckIn.created_at >= month_ago)
            .order_by(CheckIn.created_at)
        )
        checkins = result.scalars().all()

        # Последние тесты
        test_result = await session.execute(
            select(TestResult)
            .where(TestResult.telegram_id == telegram_id)
            .order_by(TestResult.created_at.desc())
            .limit(5)
        )
        tests = test_result.scalars().all()

    if len(checkins) < 3:
        return None

    # Делим на периоды для сравнения
    recent = [c for c in checkins if c.created_at >= one_week_ago]
    previous = [c for c in checkins if two_weeks_ago <= c.created_at < one_week_ago]
    all_period = checkins

    def avg(lst, field):
        vals = [getattr(c, field) for c in lst if getattr(c, field) is not None]
        return sum(vals) / len(vals) if vals else None

    # Текущие средние
    cur_mood = avg(recent or all_period, "mood")
    cur_anxiety = avg(recent or all_period, "anxiety")
    cur_energy = avg(recent or all_period, "energy")
    cur_sleep = avg([c for c in (recent or all_period) if c.sleep_hours], "sleep_hours")

    # Предыдущие средние для дельт
    prev_mood = avg(previous, "mood") if previous else None
    prev_anxiety = avg(previous, "anxiety") if previous else None
    prev_energy = avg(previous, "energy") if previous else None
    prev_sleep = avg([c for c in previous if c.sleep_hours], "sleep_hours") if previous else None

    # Строим блок изменений для промпта
    changes = []

    def describe_change(name, cur, prev, higher_is_worse=False):
        if cur is None or prev is None:
            return f"{name}: {cur:.1f}" if cur else ""
        delta = cur - prev
        if abs(delta) < 0.3:
            return f"{name}: {cur:.1f} (стабильно)"
        direction = "вырос" if delta > 0 else "упал"
        significance = "значимо" if abs(delta) >= 1.0 else "незначительно"
        concern = ""
        if higher_is_worse and delta > 0.5:
            concern = " ⚠️"
        elif not higher_is_worse and delta < -0.5:
            concern = " ⚠️"
        return f"{name}: {prev:.1f} → {cur:.1f} ({direction} на {abs(delta):.1f}, {significance}){concern}"

    if cur_mood:
        changes.append(describe_change("Настроение", cur_mood, prev_mood))
    if cur_anxiety:
        changes.append(describe_change("Тревога", cur_anxiety, prev_anxiety, higher_is_worse=True))
    if cur_energy:
        changes.append(describe_change("Энергия", cur_energy, prev_energy))
    if cur_sleep:
        changes.append(describe_change("Сон (часов)", cur_sleep, prev_sleep))

    # Тесты
    test_lines = []
    if tests:
        for tr in tests[:3]:
            test_lines.append(f"{tr.test_name}: {tr.score} баллов ({tr.level}), дата: {tr.created_at.strftime('%d.%m')}")

    # Рекомендация пройти тест если давно не проходил
    test_suggestion = ""
    if tests:
        days_since_test = (datetime.utcnow() - tests[0].created_at).days
        if days_since_test > 14:
            test_suggestion = f"Последний тест был {days_since_test} дней назад — возможно стоит пройти повторно чтобы сравнить динамику."

    if not GROQ_API_KEY and not GEMINI_API_KEY:
        return _build_basic_insights(cur_mood, cur_anxiety, cur_energy, cur_sleep, lang)

    lang_name = _LANG_NAMES.get(lang, _LANG_NAMES["ru"])

    changes_text = "\n".join(f"- {c}" for c in changes if c)
    tests_text = "\n".join(f"- {t}" for t in test_lines) if test_lines else "нет данных"

    prompt = f"""Данные пользователя за последние 30 дней ({len(checkins)} чек-инов).

ДИНАМИКА ПОКАЗАТЕЛЕЙ (текущая неделя vs предыдущая):
{changes_text}

РЕЗУЛЬТАТЫ ТЕСТОВ:
{tests_text}
{test_suggestion}

Напиши анализ на {lang_name} языке:
1. Отреагируй ТОЛЬКО на те показатели где есть значимые изменения (⚠️ — приоритет)
2. Для каждого проблемного показателя — одну конкретную практику с инструкцией как выполнить прямо сейчас
3. Если тест давно не проходился — предложи пройти конкретный тест с объяснением зачем
4. Если всё стабильно — скажи коротко и не придумывай проблем

Объём: 4-6 предложений максимум. Без воды."""

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT_INSIGHTS},
        {"role": "user", "content": prompt}
    ]

    try:
        res = await _call_ai(messages=messages, max_tokens=500, temperature=0.7)
        if res:
            return res
    except Exception as e:
        logger.error(f"Error getting correlation insights from AI: {e}")

    return _build_basic_insights(cur_mood, cur_anxiety, cur_energy, cur_sleep, lang)


def _build_basic_insights(avg_mood, avg_anxiety, avg_energy, avg_sleep, lang: str = "ru"):
    lines = []
    if avg_mood:
        lines.append(t(lang, "insights_basic_mood", avg_mood=f"{avg_mood:.1f}"))
    if avg_anxiety:
        lines.append(t(lang, "insights_basic_anxiety", avg_anxiety=f"{avg_anxiety:.1f}"))
    if avg_energy:
        lines.append(t(lang, "insights_basic_energy", avg_energy=f"{avg_energy:.1f}"))
    if avg_sleep:
        lines.append(t(lang, "insights_basic_sleep", avg_sleep=f"{avg_sleep:.1f}"))
    return "\n".join(f"• {l}" for l in lines)
