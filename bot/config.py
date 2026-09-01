import os
from dotenv import load_dotenv

load_dotenv(override=False)

def _find_env(*names, contains_keyword=None) -> str:
    """Ищет переменную окружения точно, регистронезависимо или по вхождению ключевого слова."""
    # 1. Точный поиск
    for name in names:
        val = os.environ.get(name)
        if val:
            return val

    # 2. Регистронезависимый поиск
    lower_names = {n.lower() for n in names}
    for k, v in os.environ.items():
        if k.lower() in lower_names and v:
            return v

    # 3. Поиск по ключевому слову (например 'gemini' или 'groq')
    if contains_keyword:
        kw = contains_keyword.lower()
        for k, v in os.environ.items():
            if kw in k.lower() and v and len(v.strip()) > 10:
                return v

    return None

BOT_TOKEN = _find_env("BOT_TOKEN", "TELEGRAM_BOT_TOKEN", "TOKEN", contains_keyword="token")
DATABASE_URL = _find_env("DATABASE_URL") or "sqlite:///./mental_health.db"

# AI Провайдеры
GROQ_API_KEY = _find_env("GROQ_API_KEY", "GROQ_KEY", "GROQ_TOKEN", contains_keyword="groq")
GEMINI_API_KEY = _find_env(
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "GEMINI_KEY",
    "GOOGLE_GEMINI_API_KEY",
    "GEMINI_TOKEN",
    "GOOGLE_KEY",
    contains_keyword="gemini"
)

# Лимиты для бесплатного тарифа
DAILY_FREE_AI_LIMIT = int(_find_env("DAILY_FREE_AI_LIMIT") or 25)