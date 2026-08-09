"""
Обработчик свободных сообщений — "умный чат" с MindCheck.

Этот роутер подключается ПОСЛЕДНИМ в main.py, поэтому срабатывает
только если сообщение не подошло ни одному другому хендлеру
(тесты, чек-ин, кнопки меню и т.д.).

Пользователь пишет что угодно → бот смотрит его данные в БД
→ отвечает в контексте его психологического состояния.
"""

import logging
from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from database.db import AsyncSessionLocal
from database.models import CheckIn, TestResult
from sqlalchemy import select
from datetime import datetime, timedelta

import aiohttp
from bot.config import GROQ_API_KEY, BOT_TOKEN
from bot.services.localization import t

logger = logging.getLogger("chat_handler")

router = Router()

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

SYSTEM_PROMPT = """Ты MindCheck — помощник по психологическому самонаблюдению в Telegram.

У тебя есть доступ к данным пользователя: чек-ины (настроение, тревога, энергия, сон) и результаты психологических тестов.

Твоя роль:
- Отвечать на вопросы пользователя о его состоянии, динамике, результатах тестов
- Давать конкретные практики самопомощи когда уместно
- Поддерживать живой разговор — не быть роботом

Границы (строго):
- Ты НЕ психолог и НЕ врач — не ставь диагнозы, не назначай лечение
- Опирайся только на данные которые есть — не придумывай
- При серьёзных признаках (суицидальные мысли, тяжёлая депрессия) — направляй к специалисту
- Если данных мало — честно скажи об этом

Стиль:
- Тепло, конкретно, как умный заботливый друг
- Короткие ответы (3-5 предложений) если вопрос простой
- Развёрнуто только если пользователь просит анализ"""


async def get_user_context(telegram_id: int) -> str:
    """Собирает контекст пользователя из БД для передачи в промпт."""
    async with AsyncSessionLocal() as session:
        month_ago = datetime.utcnow() - timedelta(days=30)
        week_ago = datetime.utcnow() - timedelta(days=7)

        # Чек-ины за месяц
        result = await session.execute(
            select(CheckIn)
            .where(CheckIn.telegram_id == telegram_id)
            .where(CheckIn.created_at >= month_ago)
            .order_by(CheckIn.created_at.desc())
            .limit(30)
        )
        checkins = result.scalars().all()

        # Все тесты
        test_result = await session.execute(
            select(TestResult)
            .where(TestResult.telegram_id == telegram_id)
            .order_by(TestResult.created_at.desc())
            .limit(10)
        )
        tests = test_result.scalars().all()

    if not checkins and not tests:
        return "Данных пока нет — пользователь только начал использовать бот."

    lines = []

    # Статистика чек-инов
    if checkins:
        recent = [c for c in checkins if c.created_at >= week_ago]
        avg = lambda lst, f: sum(getattr(c, f) for c in lst if getattr(c, f)) / len(lst) if lst else None

        lines.append(f"ЧЕК-ИНЫ за последние 30 дней: {len(checkins)} записей")
        if recent:
            m = avg(recent, 'mood')
            a = avg(recent, 'anxiety')
            e = avg(recent, 'energy')
            s = avg([c for c in recent if c.sleep_hours], 'sleep_hours')
            lines.append(f"Последняя неделя: настроение {m:.1f}/10, тревога {a:.1f}/10, энергия {e:.1f}/10" + (f", сон {s:.1f}ч" if s else ""))

        # Последние 5 чек-инов
        lines.append("Последние чек-ины:")
        for c in checkins[:5]:
            date = c.created_at.strftime('%d.%m')
            sleep_str = f", сон {c.sleep_hours}ч" if c.sleep_hours else ""
            lines.append(f"  {date}: настроение {c.mood}, тревога {c.anxiety}, энергия {c.energy}{sleep_str}")

    # Тесты
    if tests:
        lines.append("РЕЗУЛЬТАТЫ ТЕСТОВ (от новых к старым):")
        for tr in tests:
            date = tr.created_at.strftime('%d.%m.%Y')
            lines.append(f"  {date} | {tr.test_name}: {tr.score} баллов ({tr.level})")

    return "\n".join(lines)


@router.message(F.text & ~F.text.startswith('/'))
async def handle_free_text(message: Message, state: FSMContext):
    """
    Перехватывает любое текстовое сообщение которое не является командой
    и не было обработано другими роутерами.
    """
    current_state = await state.get_state()
    if current_state:
        # Пользователь в процессе теста или чек-ина — не перебиваем
        return

    if not GROQ_API_KEY:
        await message.answer("AI-чат временно недоступен.")
        return

    # Определяем язык пользователя
    lang = "ru"  # дефолт, можно улучшить если есть хранение языка

    # Собираем контекст пользователя
    user_context = await get_user_context(message.from_user.id)

    user_prompt = f"""Данные пользователя:
{user_context}

Вопрос/сообщение пользователя: {message.text}"""

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ],
        "max_tokens": 500,
        "temperature": 0.8
    }

    try:
        await message.bot.send_chat_action(message.chat.id, "typing")
        async with aiohttp.ClientSession() as session:
            async with session.post(GROQ_URL, headers=headers, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    reply = data["choices"][0]["message"]["content"]
                    await message.answer(reply)
                else:
                    await message.answer(t(lang, "error_ai_unavailable") if False else "Не удалось получить ответ. Попробуй ещё раз.")
    except Exception as e:
        logger.error(f"Chat handler error: {e}")
        await message.answer("Что-то пошло не так. Попробуй ещё раз.")
