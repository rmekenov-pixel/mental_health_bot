import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./mental_health.db")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
