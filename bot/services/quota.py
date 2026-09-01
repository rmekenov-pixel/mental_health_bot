"""
Сервис управления квотами и лимитами пользователей (User Quota & Rate Limiting).
Ограничивает количество обращений к AI в сутки для бесплатных пользователей,
предотвращая перегрузку API и создавая базу для монетизации (Freemium).
"""

from datetime import datetime
from sqlalchemy import select
from database.db import AsyncSessionLocal
from database.models import User
from bot.config import DAILY_FREE_AI_LIMIT

_LIMIT_EXCEEDED_MESSAGES = {
    "ru": (
        "⏳ <b>Дневной лимит AI-сообщений исчерпан</b>\n\n"
        f"Ты использовал все {DAILY_FREE_AI_LIMIT} бесплатных обращений к AI на сегодня. "
        "Лимит обновится завтра утром.\n\n"
        "💡 <i>Чек-ины, прохождение психологических тестов и просмотр графиков остаются полностью бесплатными и безлимитными!</i>"
    ),
    "kz": (
        "⏳ <b>Бүгінгі күнге арналған AI хабарламаларының лимиті бітті</b>\n\n"
        f"Сіз бүгінгі {DAILY_FREE_AI_LIMIT} тегін AI сұрауын толық пайдаландыңыз. "
        "Лимит ертең таңертең жаңарады.\n\n"
        "💡 <i>Күнделікті чек-индер, тесттерден өту және графиктерді көру толықтай тегін әрі шектеусіз қала береді!</i>"
    ),
    "en": (
        "⏳ <b>Daily AI message limit reached</b>\n\n"
        f"You've used all {DAILY_FREE_AI_LIMIT} free AI requests for today. "
        "Your quota will reset tomorrow morning.\n\n"
        "💡 <i>Check-ins, psychological tests, and mood charts remain 100% free and unlimited!</i>"
    ),
}


async def check_and_increment_ai_quota(telegram_id: int) -> tuple[bool, int]:
    """
    Проверяет, не превысил ли пользователь дневной лимит AI-запросов.
    Если лимит не исчерпан, инкрементирует счетчик.
    
    Возвращает:
        (allowed: bool, remaining: int)
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            return True, DAILY_FREE_AI_LIMIT

        # Премиум-пользователи имеют безлимитный доступ
        if getattr(user, "is_premium", False):
            return True, 9999

        now = datetime.utcnow()
        last_req = user.last_ai_request_date

        # Сброс счетчика, если наступил новый день (по UTC)
        if not last_req or last_req.date() < now.date():
            user.daily_ai_count = 0

        if (user.daily_ai_count or 0) >= DAILY_FREE_AI_LIMIT:
            return False, 0

        user.daily_ai_count = (user.daily_ai_count or 0) + 1
        user.last_ai_request_date = now
        await session.commit()

        remaining = DAILY_FREE_AI_LIMIT - user.daily_ai_count
        return True, remaining


def get_limit_exceeded_message(lang: str = "ru") -> str:
    """Возвращает локализованное сообщение об исчерпании дневного лимита."""
    return _LIMIT_EXCEEDED_MESSAGES.get(lang, _LIMIT_EXCEEDED_MESSAGES["ru"])
