import aiohttp
import json
from bot.config import GROQ_API_KEY

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


async def get_ai_explanation(test_name: str, score: int, level: str) -> str:
    if not GROQ_API_KEY:
        return "AI-объяснение недоступно."

    prompt = f"""Пользователь прошёл психологический тест {test_name} и получил {score} баллов. Уровень: {level}.

Напиши короткое, тёплое объяснение (3-4 предложения):
1. Что означает этот результат простыми словами
2. Одну мягкую рекомендацию
3. Напомни что это не диагноз

Пиши на русском языке, без медицинских терминов, без запугивания."""

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "llama3-8b-8192",
        "messages": [
            {
                "role": "system",
                "content": "Ты заботливый помощник по психологическому здоровью. Ты НЕ психолог и НЕ врач. Ты помогаешь людям понять результаты тестов простым языком."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "max_tokens": 300,
        "temperature": 0.7
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(GROQ_URL, headers=headers, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    return data["choices"][0]["message"]["content"]
                else:
                    return "AI-объяснение временно недоступно."
    except Exception:
        return "AI-объяснение временно недоступно."