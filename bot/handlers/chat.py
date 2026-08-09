"""
Обработчик свободных сообщений — "умный чат" с MindCheck.

Улучшения v2:
- Язык берётся из БД (поле User.language)
- История диалога хранится в FSM (память в рамках сессии)
- Промпт явно требует отвечать на языке пользователя
"""

import logging
from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from database.db import AsyncSessionLocal
from database.models import CheckIn, TestResult, User
from sqlalchemy import select
from datetime import datetime, timedelta

import aiohttp
from bot.config import GROQ_API_KEY

logger = logging.getLogger("chat_handler")

router = Router()

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# Максимум сообщений в истории диалога (пар вопрос-ответ)
MAX_HISTORY = 6

LANG_NAMES = {
    "ru": "русском",
    "kz": "казахском",
    "en": "English",
}

def build_system_prompt(lang: str) -> str:
    lang_name = LANG_NAMES.get(lang, "русском")
    return f"""Ты MindCheck — помощник по психологическому самонаблюдению в Telegram.

У тебя есть доступ к данным пользователя: чек-ины (настроение, тревога, энергия, сон) и результаты психологических тестов.

Твоя роль:
- Отвечать на вопросы пользователя о его состоянии, динамике, результатах тестов
- Давать конкретные практики самопомощи с инструкцией когда уместно
- Поддерживать живой разговор — не быть роботом

Границы (строго):
- Ты НЕ психолог и НЕ врач — не ставь диагнозы, не назначай лечение
- Опирайся только на данные которые есть — не придумывай
- При серьёзных признаках (суицидальные мысли, тяжёлая депрессия) — направляй к специалисту
- Если данных мало — честно скажи об этом

Стиль:
- Тепло, конкретно, как умный заботливый друг
- Короткие ответы (3-5 предложений) если вопрос простой
- Развёрнуто только если пользователь просит анализ

ВАЖНО: Отвечай ТОЛЬКО на {lang_name} языке. Не переключайся на другие языки ни при каких условиях."""


async def get_user_lang(telegram_id: int) -> str:
    """Получает язык пользователя из БД."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        return user.language if user and user.language else "ru"


async def get_user_context(telegram_id: int) -> str:
    """Собирает контекст пользователя из БД для передачи в промпт."""
    async with AsyncSessionLocal() as session:
        month_ago = datetime.utcnow() - timedelta(days=30)
        week_ago = datetime.utcnow() - timedelta(days=7)

        result = await session.execute(
            select(CheckIn)
            .where(CheckIn.telegram_id == telegram_id)
            .where(CheckIn.created_at >= month_ago)
            .order_by(CheckIn.created_at.desc())
            .limit(30)
        )
        checkins = result.scalars().all()

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

    if checkins:
        recent = [c for c in checkins if c.created_at >= week_ago]

        def avg(lst, f):
            vals = [getattr(c, f) for c in lst if getattr(c, f) is not None]
            return sum(vals) / len(vals) if vals else None

        lines.append(f"ЧЕК-ИНЫ за последние 30 дней: {len(checkins)} записей")
        if recent:
            m = avg(recent, 'mood')
            a = avg(recent, 'anxiety')
            e = avg(recent, 'energy')
            s = avg([c for c in recent if c.sleep_hours], 'sleep_hours')
            parts = [f"настроение {m:.1f}/10", f"тревога {a:.1f}/10", f"энергия {e:.1f}/10"]
            if s:
                parts.append(f"сон {s:.1f}ч")
            lines.append(f"Последняя неделя: {', '.join(parts)}")

        lines.append("Последние чек-ины:")
        for c in checkins[:5]:
            date = c.created_at.strftime('%d.%m')
            sleep_str = f", сон {c.sleep_hours}ч" if c.sleep_hours else ""
            lines.append(f"  {date}: настроение {c.mood}, тревога {c.anxiety}, энергия {c.energy}{sleep_str}")

    if tests:
        lines.append("РЕЗУЛЬТАТЫ ТЕСТОВ (от новых к старым):")
        for tr in tests:
            date = tr.created_at.strftime('%d.%m.%Y')
            lines.append(f"  {date} | {tr.test_name}: {tr.score} баллов ({tr.level})")

    return "\n".join(lines)


@router.message(F.text & ~F.text.startswith('/'))
async def handle_free_text(message: Message, state: FSMContext):
    """
    Перехватывает свободные сообщения, отвечает с контекстом данных пользователя.
    Хранит историю диалога в FSM на время сессии.
    """
    current_state = await state.get_state()
    if current_state:
        return

    if not GROQ_API_KEY:
        await message.answer("AI-чат временно недоступен.")
        return

    # Язык из БД
    lang = await get_user_lang(message.from_user.id)

    # Контекст данных пользователя
    user_context = await get_user_context(message.from_user.id)

    # История диалога из FSM
    data = await state.get_data()
    chat_history = data.get("chat_history", [])

    # Добавляем новое сообщение пользователя
    # Контекст данных передаём только в первом сообщении или если история пустая
    if not chat_history:
        user_content = f"""Данные пользователя:
{user_context}

Вопрос: {message.text}"""
    else:
        user_content = message.text

    chat_history.append({"role": "user", "content": user_content})

    # Обрезаем историю если слишком длинная (MAX_HISTORY пар = MAX_HISTORY*2 сообщений)
    if len(chat_history) > MAX_HISTORY * 2:
        # Оставляем первое сообщение (с контекстом данных) + последние N-1 пар
        chat_history = chat_history[:1] + chat_history[-(MAX_HISTORY * 2 - 1):]

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": build_system_prompt(lang)},
            *chat_history
        ],
        "max_tokens": 500,
        "temperature": 0.8
    }

    try:
        await message.bot.send_chat_action(message.chat.id, "typing")
        async with aiohttp.ClientSession() as session:
            async with session.post(GROQ_URL, headers=headers, json=payload) as response:
                if response.status == 200:
                    data_resp = await response.json()
                    reply = data_resp["choices"][0]["message"]["content"]

                    # Сохраняем ответ в историю
                    chat_history.append({"role": "assistant", "content": reply})
                    await state.update_data(chat_history=chat_history)

                    await message.answer(reply)
                else:
                    await message.answer("Не удалось получить ответ. Попробуй ещё раз.")
    except Exception as e:
        logger.error(f"Chat handler error: {e}")
        await message.answer("Что-то пошло не так. Попробуй ещё раз.")
