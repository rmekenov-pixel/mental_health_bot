"""
Обработчик свободных сообщений — "умный чат" с MindCheck.

Улучшения:
- Развёрнутые, глубокие и практически применимые ответы без обрезки сообщений (max_tokens=1200)
- Тёплый, поддерживающий тон с конкретными пошаговыми техниками (КПТ, дыхание, сон, энергия)
- SAFETY: Немедленный перехват суицидальных кризисов без обращения к AI
- QUOTA: Суточные лимиты на пользователя (25 бесплатных AI-сообщений в день)
"""

import time
import logging
from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from database.db import AsyncSessionLocal
from database.models import CheckIn, TestResult, User
from sqlalchemy import select
from datetime import datetime, timedelta

from bot.config import GROQ_API_KEY, GEMINI_API_KEY
from bot.services.ai_explanation import _call_ai, get_gemini_key, get_groq_key
from bot.services.crisis import is_crisis_text, get_crisis_message
from bot.services.quota import check_and_increment_ai_quota, get_limit_exceeded_message

logger = logging.getLogger("chat_handler")

router = Router()

MAX_HISTORY = 6
_USER_LAST_REQUEST = {}
USER_COOLDOWN_SECONDS = 2.0

LANG_NAMES = {
    "ru": "русском",
    "kz": "казахском",
    "en": "English",
}


def build_system_prompt(lang: str) -> str:
    lang_name = LANG_NAMES.get(lang, "русском")
    return f"""Ты MindCheck — тёплый, внимательный и профессиональный ассистент по психологическому самонаблюдению в Telegram.

Твоя главная цель — дать человеку действительно работающую, глубокую и понятную помощь, основанную на доказательной психологии (КПТ, физиология стресса, гигиена сна, майндфулнес).

ПРАВИЛА ОТВЕТА:
1. Пиши на безупречно красивом, естественном и живом {lang_name} языке. Никаких сухих шаблонов и роботизированных фраз.
2. Будь МАКСИМАЛЬНО КОНКРЕТЕН: не говори общими словами вроде "отдыхай" или "питайся правильно". Давай конкретные шаги и инструкции:
   - Если советуешь технику — опиши: 1) как сесть/встать, 2) как дышать (счёт секунд), 3) сколько минут делать.
   - Если вопрос про энергию и сон — объясняй физиологическую причину (кортизол, дофамин, фазы глубокого сна) и давай альтернативы (без клише).
3. Форматируй сообщение красиво: используй понятные списки, жирный шрифт для ключевых мыслей и разделители.
4. ВСЕГДА заканчивай ответ логичным завершением и словами поддержки. Никогда не обрывай фразы.
5. Ты НЕ врач: не ставь диагнозы и не назначай препараты. Если видишь признаки острого кризиса — мягко порекомендуй специалиста."""


async def get_user_lang(telegram_id: int) -> str:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        return user.language if user and user.language else "ru"


async def get_user_context(telegram_id: int) -> str:
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
    current_state = await state.get_state()
    if current_state:
        return

    lang = await get_user_lang(message.from_user.id)

    # 1. SAFETY: Перехват кризисов
    if is_crisis_text(message.text):
        logger.warning(f"CRISIS TRIGGER DETECTED for user {message.from_user.id}: {message.text[:50]}")
        await message.answer(get_crisis_message(lang), parse_mode="HTML")
        return

    # 2. Rate limiting
    now = time.time()
    last_req = _USER_LAST_REQUEST.get(message.from_user.id, 0)
    if now - last_req < USER_COOLDOWN_SECONDS:
        return
    _USER_LAST_REQUEST[message.from_user.id] = now

    # 3. Проверка квоты
    allowed, remaining = await check_and_increment_ai_quota(message.from_user.id)
    if not allowed:
        await message.answer(get_limit_exceeded_message(lang), parse_mode="HTML")
        return

    if not get_groq_key() and not get_gemini_key():
        await message.answer("AI-чат временно настраивается администратором.")
        return

    user_context = await get_user_context(message.from_user.id)

    data = await state.get_data()
    chat_history = data.get("chat_history", [])

    if not chat_history:
        user_content = f"""Данные самонаблюдения пользователя за последние дни:
{user_context}

Вопрос пользователя: {message.text}"""
    else:
        user_content = message.text

    outgoing_history = list(chat_history)
    outgoing_history.append({"role": "user", "content": user_content})

    if len(outgoing_history) > MAX_HISTORY * 2:
        outgoing_history = outgoing_history[:1] + outgoing_history[-(MAX_HISTORY * 2 - 1):]

    messages = [
        {"role": "system", "content": build_system_prompt(lang)},
        *outgoing_history
    ]

    try:
        await message.bot.send_chat_action(message.chat.id, "typing")
        reply = await _call_ai(messages=messages, max_tokens=1200, temperature=0.6)

        if reply:
            chat_history.append({"role": "user", "content": message.text})
            chat_history.append({"role": "assistant", "content": reply})
            await state.update_data(chat_history=chat_history)
            await message.answer(reply)
        else:
            await message.answer("Не удалось получить ответ от AI. Попробуй ещё раз через минуту.")
    except Exception as e:
        logger.error(f"Chat handler error: {e}")
        await message.answer("Что-то пошло не так при обращении к AI. Попробуй ещё раз.")
