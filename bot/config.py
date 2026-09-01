import os
from dotenv import load_dotenv

load_dotenv(override=False)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./mental_health.db")

# AI Провайдеры
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Лимиты для бесплатного тарифа (сообщений к AI в день на пользователя)
DAILY_FREE_AI_LIMIT = int(os.environ.get("DAILY_FREE_AI_LIMIT", 25))