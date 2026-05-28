import os
from dotenv import load_dotenv

load_dotenv(override=False)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8992809126:AAG2D9UMhcznMAF8w_d_nHsXXcmRNHVBZ-0")
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./mental_health.db")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")