import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.environ.get("BOT_TOKEN")
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./mental_health.db")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")