import json
import os

_cache = {}


def load_locale(lang: str) -> dict:
    if lang in _cache:
        return _cache[lang]
    
    path = os.path.join("locales", f"{lang}.json")
    if not os.path.exists(path):
        path = os.path.join("locales", "ru.json")
    
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    _cache[lang] = data
    return data


def t(lang: str, key: str, **kwargs) -> str:
    locale = load_locale(lang)
    text = locale.get(key, key)
    if kwargs:
        try:
            text = text.format(**kwargs)
        except Exception:
            pass
    return text


def get_lang(user) -> str:
    if hasattr(user, 'language') and user.language:
        return user.language
    return "ru"

async def get_user_lang(telegram_id: int) -> str:
    from database.db import AsyncSessionLocal
    from database.models import User
    from sqlalchemy import select
    
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            user = result.scalar_one_or_none()
            if user and user.language:
                return user.language
    except Exception:
        pass
    return "ru"