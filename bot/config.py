import os
from dotenv import load_dotenv

load_dotenv(override=False)

def _find_env(*names) -> str:
    """Ищет переменную окружения с учетом регистра и без него."""
    for name in names:
        val = os.environ.get(name)
        if val:
            return val
    # Регистронезависимый поиск по всем переменным
    lower_names = {n.lower() for n in names}
    for k, v in os.environ.items():
        if k.lower() in lower_names and v:
            return v
    return None

BOT_TOKEN = _find_env("BOT_TOKEN", "TELEGRAM_BOT_TOKEN", "TOKEN")
DATABASE_URL = _find_env("DATABASE_URL") or "sqlite:///./mental_health.db"

# AI Провайдеры
GROQ_API_KEY = _find_env("GROQ_API_KEY", "GROQ_KEY", "GROQ_TOKEN")
GEMINI_API_KEY = _find_env(
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "GEMINI_KEY",
    "GOOGLE_GEMINI_API_KEY",
    "GEMINI_TOKEN",
    "GOOGLE_KEY"
)

# Лимиты для бесплатного тарифа
DAILY_FREE_AI_LIMIT = int(_find_env("DAILY_FREE_AI_LIMIT") or 25)