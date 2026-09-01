import aiohttp
import logging
from bot.config import GROQ_API_KEY, GEMINI_API_KEY

logger = logging.getLogger("ai_explanation")

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# Список моделей Groq для автоматического перебора при смене/декомиссии
GROQ_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "llama-3.1-70b-versatile",
    "gemma2-9b-it",
    "mixtral-8x7b-32768",
]

# Кэш готовых объяснений тестов (test_name:score:lang -> explanation_text)
_TEST_EXPLANATION_CACHE = {}

_LANG_NAMES = {
    "ru": "русском",
    "kz": "казахском",
    "en": "English",
}

_FALLBACK_NO_KEY = {
    "ru": "AI-сервис временно настраивается администратором.",
    "kz": "AI қызметі уақытша бапталуда.",
    "en": "AI service is currently being configured.",
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


async def _call_gemini_native(messages: list, max_tokens: int = 500, temperature: float = 0.8) -> str:
    """Выполняет прямой запрос к Google Gemini REST API."""
    if not GEMINI_API_KEY:
        return None

    system_text = ""
    contents = []
    for m in messages:
        role = m.get("role")
        text = m.get("content", "")
        if role == "system":
            system_text = text
        elif role == "user":
            contents.append({"role": "user", "parts": [{"text": text}]})
        elif role == "assistant":
            contents.append({"role": "model", "parts": [{"text": text}]})

    payload = {
        "contents": contents,
        "generationConfig": {
            "maxOutputTokens": max_tokens,
            "temperature": temperature
        }
    }
    if system_text:
        payload["system_instruction"] = {
            "parts": [{"text": system_text}]
        }

    timeout = aiohttp.ClientTimeout(total=20)

    # Пробуем доступные модели Gemini
    for model in ["gemini-1.5-flash", "gemini-2.0-flash", "gemini-1.5-flash-latest"]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        candidates = data.get("candidates", [])
                        if candidates and "content" in candidates[0]:
                            parts = candidates[0]["content"].get("parts", [])
                            if parts:
                                return parts[0].get("text", "").strip()
                    else:
                        err_body = await response.text()
                        logger.error(f"Gemini API error ({model}) HTTP {response.status}: {err_body}")
        except Exception as e:
            logger.error(f"Gemini request exception ({model}): {e}")

    return None


async def _call_groq(messages: list, max_tokens: int = 400, temperature: float = 0.8) -> str:
    """Выполняет запрос к Groq API с перебором активных моделей."""
    if not GROQ_API_KEY:
        return None

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    timeout = aiohttp.ClientTimeout(total=20)

    for model in GROQ_MODELS:
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature
        }
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(GROQ_URL, headers=headers, json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data["choices"][0]["message"]["content"].strip()
                    else:
                        err_body = await response.text()
                        logger.error(f"Groq API error ({model}) HTTP {response.status}: {err_body}")
        except Exception as e:
            logger.error(f"Groq API request exception ({model}): {e}")

    return None


async def _call_ai(messages: list, max_tokens: int = 500, temperature: float = 0.8) -> str:
    """
    Главная точка входа в AI.
    1. Пробует Google Gemini (1 000 000 TPM бесплатно).
    2. При ошибке или отсутствии ключа — переключается на Groq (Llama).
    """
    # 1. Приоритет: Google Gemini
    if GEMINI_API_KEY:
        res = await _call_gemini_native(messages, max_tokens, temperature)
        if res:
            return res

    # 2. Резерв: Groq Cloud
    if GROQ_API_KEY:
        res = await _call_groq(messages, max_tokens, temperature)
        if res:
            return res

    if not GEMINI_API_KEY and not GROQ_API_KEY:
        logger.error("No AI keys found (neither GEMINI_API_KEY nor GROQ_API_KEY set).")

    return None


async def get_ai_explanation(test_name: str, score: int, level: str, lang: str = "ru") -> str:
    cache_key = f"{test_name}:{score}:{level}:{lang}"
    if cache_key in _TEST_EXPLANATION_CACHE:
        return _TEST_EXPLANATION_CACHE[cache_key]

    if not GROQ_API_KEY and not GEMINI_API_KEY:
        return _FALLBACK_NO_KEY.get(lang, _FALLBACK_NO_KEY["ru"])

    lang_name = _LANG_NAMES.get(lang, _LANG_NAMES["ru"])

    prompt = f"""Пользователь прошёл тест "{test_name}" и получил {score} баллов. Уровень: {level}.

Напиши объяснение на {lang_name} языке (3-4 предложения):
1. Что означает этот результат — простыми словами, без страшилок
2. Одну-две конкретные практики которые реально помогут при таком результате — назови технику и объясни как её выполнить прямо сейчас
3. Напомни что это самонаблюдение, не диагноз"""

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT_EXPLANATION},
        {"role": "user", "content": prompt}
    ]

    result = await _call_ai(messages=messages, max_tokens=400, temperature=0.8)
    if result:
        _TEST_EXPLANATION_CACHE[cache_key] = result
        return result

    return _FALLBACK_UNAVAILABLE_EXPLANATION.get(lang, _FALLBACK_UNAVAILABLE_EXPLANATION["ru"])


async def get_ai_weekly_reflection(avg_mood: float, avg_anxiety: float, avg_energy: float, checkin_count: int, lang: str = "ru") -> str:
    if not GROQ_API_KEY and not GEMINI_API_KEY:
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

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT_REFLECTION},
        {"role": "user", "content": prompt}
    ]

    result = await _call_ai(messages=messages, max_tokens=400, temperature=0.8)
    if result:
        return result

    return _FALLBACK_UNAVAILABLE_REFLECTION.get(lang, _FALLBACK_UNAVAILABLE_REFLECTION["ru"])
