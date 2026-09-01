import aiohttp
import logging
from bot.config import GROQ_API_KEY, GEMINI_API_KEY

logger = logging.getLogger("ai_explanation")

# Эндпоинты провайдеров
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"

GROQ_PRIMARY_MODEL = "llama-3.3-70b-versatile"
GROQ_FALLBACK_MODEL = "llama-3.1-8b-instant"
GEMINI_MODEL = "gemini-2.0-flash"

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


async def _call_ai(messages: list, max_tokens: int = 400, temperature: float = 0.8) -> str:
    """
    Выполняет запрос к AI с многоуровневым каскадом отказоустойчивости:
    1. Google Gemini 2.0 Flash (если задан GEMINI_API_KEY — 1M токенов/мин)
    2. Groq Llama 3.3 70B (если задан GROQ_API_KEY)
    3. Groq Llama 3.1 8B (резервный сверхбыстрый)
    """
    timeout = aiohttp.ClientTimeout(total=25)

    # 1. Пробуем Google Gemini Flash
    if GEMINI_API_KEY:
        gemini_headers = {
            "Authorization": f"Bearer {GEMINI_API_KEY}",
            "Content-Type": "application/json"
        }
        gemini_payload = {
            "model": GEMINI_MODEL,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature
        }
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(GEMINI_URL, headers=gemini_headers, json=gemini_payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data["choices"][0]["message"]["content"]
                    else:
                        err_body = await response.text()
                        logger.warning(f"Gemini API returned HTTP {response.status}: {err_body}")
        except Exception as e:
            logger.warning(f"Gemini API exception: {e}")

    # 2. Пробуем Groq API (основная 70b, затем запасная 8b)
    if GROQ_API_KEY:
        groq_headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        for model in [GROQ_PRIMARY_MODEL, GROQ_FALLBACK_MODEL]:
            payload = {
                "model": model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature
            }
            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(GROQ_URL, headers=groq_headers, json=payload) as response:
                        if response.status == 200:
                            data = await response.json()
                            return data["choices"][0]["message"]["content"]
                        else:
                            err_body = await response.text()
                            logger.error(f"Groq API error ({model}) HTTP {response.status}: {err_body}")
            except Exception as e:
                logger.error(f"Groq API exception ({model}): {e}")

    if not GEMINI_API_KEY and not GROQ_API_KEY:
        logger.error("No AI API keys configured (neither GEMINI_API_KEY nor GROQ_API_KEY found).")

    return None


async def get_ai_explanation(test_name: str, score: int, level: str, lang: str = "ru") -> str:
    # 1. Проверяем кэш результатов
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
        # Сохраняем в кэш для мгновенной отдачи при повторных результатах
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
