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

SYSTEM_PROMPT_EXPLANATION = """Ты тёплый и внимательный помощник по психологическому самонаблюдению.

Твоя роль:
- Помочь человеку понять что означает результат теста простым языком
- Предложить практические техники самопомощи основанные на доказательной психологии (КПТ, майндфулнес, поведенческая активация и др.)
- Поддержать и нормализовать переживания

Границы (строго):
- Ты НЕ психолог и НЕ врач — не ставь диагнозы, не назначай лечение
- Не пугай и не драматизируй результаты
- При серьёзных показателях мягко рекомендуй обратиться к специалисту

Стиль:
- Тепло, конкретно, без клише и банальностей
- Техники называй по имени и объясняй КАК выполнить (не просто "попробуй медитацию", а реальная инструкция)
- Каждый ответ уникален — адаптируй к конкретным данным человека, не шаблонь"""

SYSTEM_PROMPT_REFLECTION = """Ты тёплый и внимательный помощник по психологическому самонаблюдению.

Твоя роль:
- Анализировать динамику состояния человека за период
- Замечать паттерны и связи между показателями
- Предлагать конкретные практики самопомощи из доказательной психологии

Границы (строго):
- Ты НЕ психолог и НЕ врач — не ставь диагнозы, не назначай лечение
- Не используй общие фразы без смысла ("занимайся тем что нравится", "надейся", "береги себя")
- Каждая рекомендация должна быть конкретной: что именно делать, как, сколько времени

Стиль:
- Говори как умный заботливый друг который разбирается в психологии
- Опирайся строго на данные — не придумывай то чего нет в цифрах
- Варьируй рекомендации: смотри на данные и думай что реально поможет этому человеку сейчас"""


async def get_ai_explanation(test_name: str, score: int, level: str, lang: str = "ru") -> str:
    if not GROQ_API_KEY:
        return _FALLBACK_NO_KEY.get(lang, _FALLBACK_NO_KEY["ru"])

    lang_name = _LANG_NAMES.get(lang, _LANG_NAMES["ru"])

    prompt = f"""Пользователь прошёл тест "{test_name}" и получил {score} баллов. Уровень: {level}.

Напиши объяснение на {lang_name} языке (3-4 предложения):
1. Что означает этот результат — простыми словами, без страшилок
2. Одну-две конкретные практики которые реально помогут при таком результате — назови технику и объясни как её выполнить прямо сейчас
3. Напомни что это самонаблюдение, не диагноз"""

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT_EXPLANATION},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 400,
        "temperature": 0.8
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

    prompt = f"""Пользователь отслеживал состояние {checkin_count} дней за неделю.

Средние показатели:
- Настроение: {avg_mood:.1f}/10
- Тревога: {avg_anxiety:.1f}/10
- Энергия: {avg_energy:.1f}/10

Напиши анализ недели на {lang_name} языке (3-4 предложения):
1. Что говорят эти цифры о состоянии человека — честно и тепло
2. Что конкретно заслуживает внимания исходя из данных
3. Одну-две практики которые подходят именно к этим показателям — назови и объясни как выполнить"""

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT_REFLECTION},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 400,
        "temperature": 0.8
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
