import aiohttp
from bot.config import GROQ_API_KEY

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

_LANG_NAMES = {
    "ru": "русском",
    "kz": "казахском",
    "en": "English",
}

_FALLBACK_NO_KEY = {
    "ru": "GROQ_API_KEY не найден!",
    "kz": "GROQ_API_KEY табылмады!",
    "en": "GROQ_API_KEY not found!",
}

_FALLBACK_UNAVAILABLE_EXPLANATION = {
    "ru": "AI-объяснение временно недоступно.",
    "kz": "AI түсіндірмесі уақытша қолжетімсіз.",
    "en": "AI explanation is temporarily unavailable.",
}

_FALLBACK_UNAVAILABLE_REFLECTION = {
    "ru": "AI-анализ временно недоступен.",
    "kz": "AI талдауы уақытша қолжетімсіз.",
    "en": "AI analysis is temporarily unavailable.",
}


async def get_ai_explanation(test_name: str, score: int, level: str, lang: str = "ru") -> str:
    if not GROQ_API_KEY:
        return _FALLBACK_NO_KEY.get(lang, _FALLBACK_NO_KEY["ru"])

    lang_name = _LANG_NAMES.get(lang, _LANG_NAMES["ru"])

    prompt = f"""Пользователь прошёл психологический тест {test_name} и получил {score} баллов. Уровень: {level}.

Напиши короткое, тёплое объяснение (3-4 предложения):
1. Что означает этот результат простыми словами
2. Одну мягкую рекомендацию
3. Напомни что это не диагноз

Пиши на {lang_name} языке, без медицинских терминов, без запугивания."""

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "llama-3.3-70b-versatile",
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
                    return _FALLBACK_UNAVAILABLE_EXPLANATION.get(lang, _FALLBACK_UNAVAILABLE_EXPLANATION["ru"])
    except Exception as e:
        import logging
        logging.error(f"Groq API error: {e}")
        return _FALLBACK_UNAVAILABLE_EXPLANATION.get(lang, _FALLBACK_UNAVAILABLE_EXPLANATION["ru"])


async def get_ai_weekly_reflection(avg_mood: float, avg_anxiety: float, avg_energy: float, checkin_count: int, lang: str = "ru") -> str:
    if not GROQ_API_KEY:
        return _FALLBACK_UNAVAILABLE_REFLECTION.get(lang, _FALLBACK_UNAVAILABLE_REFLECTION["ru"])

    lang_name = _LANG_NAMES.get(lang, _LANG_NAMES["ru"])

    prompt = f"""Пользователь отслеживал своё состояние {checkin_count} дней за неделю.

Средние показатели:
- Настроение: {avg_mood:.1f}/10
- Тревога: {avg_anxiety:.1f}/10
- Энергия: {avg_energy:.1f}/10

Напиши короткий (3-4 предложения) тёплый анализ недели:
1. Общая оценка состояния
2. Что заслуживает внимания
3. Одна конкретная рекомендация на следующую неделю

Пиши на {lang_name} языке, без медицинских терминов, тепло и поддерживающе."""

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {
                "role": "system",
                "content": "Ты заботливый помощник по психологическому здоровью. Анализируй данные и давай поддерживающие советы."
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
                    return _FALLBACK_UNAVAILABLE_REFLECTION.get(lang, _FALLBACK_UNAVAILABLE_REFLECTION["ru"])
    except Exception as e:
        import logging
        logging.error(f"AI weekly reflection error: {e}")
        return _FALLBACK_UNAVAILABLE_REFLECTION.get(lang, _FALLBACK_UNAVAILABLE_REFLECTION["ru"])
