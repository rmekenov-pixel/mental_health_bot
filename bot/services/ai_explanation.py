import aiohttp
import logging
import bot.config as cfg

logger = logging.getLogger("ai_explanation")

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

def get_groq_key() -> str:
    key = cfg.GROQ_API_KEY or ""
    return key.strip().strip('"').strip("'")

def get_gemini_key() -> str:
    key = cfg.GEMINI_API_KEY or ""
    return key.strip().strip('"').strip("'")

GROQ_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "llama3-70b-8192",
    "llama3-8b-8192",
    "deepseek-r1-distill-llama-70b",
    "gemma2-9b-it",
    "mixtral-8x7b-32768",
]

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


def normalize_messages(messages: list) -> tuple[str, list]:
    """
    Нормализует список сообщений:
    - Извлекает системный промпт
    - Объединяет идущие подряд сообщения с одинаковой ролью (для Gemini API)
    - Убирает пустые сообщения
    """
    system_text = ""
    turns = []

    for m in messages:
        role = m.get("role")
        content = (m.get("content") or "").strip()
        if not content:
            continue

        if role == "system":
            if system_text:
                system_text += "\n\n" + content
            else:
                system_text = content
        elif role in ("user", "assistant"):
            if turns and turns[-1]["role"] == role:
                turns[-1]["content"] += "\n\n" + content
            else:
                turns.append({"role": role, "content": content})

    # Gemini требует чтобы диалог начинался с 'user'
    while turns and turns[0]["role"] == "assistant":
        turns.pop(0)

    return system_text, turns


async def _call_gemini_native(messages: list, max_tokens: int = 500, temperature: float = 0.8) -> tuple[str, str]:
    """
    Выполняет прямой запрос к Google Gemini REST API.
    Возвращает (content, error_reason).
    """
    gemini_key = get_gemini_key()
    if not gemini_key:
        return None, "Key not found"

    system_text, turns = normalize_messages(messages)
    if not turns:
        return None, "No messages to send"

    contents = []
    for turn in turns:
        role = "user" if turn["role"] == "user" else "model"
        contents.append({"role": role, "parts": [{"text": turn["content"]}]})

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
    last_err = "Unknown error"

    for model in ["gemini-1.5-flash", "gemini-2.0-flash", "gemini-1.5-flash-latest"]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={gemini_key}"
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        candidates = data.get("candidates", [])
                        if candidates and "content" in candidates[0]:
                            parts = candidates[0]["content"].get("parts", [])
                            if parts:
                                return parts[0].get("text", "").strip(), None
                    else:
                        err_body = await response.text()
                        last_err = f"HTTP {response.status}: {err_body[:100]}"
                        logger.error(f"Gemini API error ({model}) HTTP {response.status}: {err_body}")
        except Exception as e:
            last_err = str(e)
            logger.error(f"Gemini request exception ({model}): {e}")

    return None, last_err


async def _call_groq(messages: list, max_tokens: int = 400, temperature: float = 0.8) -> tuple[str, str]:
    """
    Выполняет запрос к Groq API с перебором активных моделей.
    Возвращает (content, error_reason).
    """
    groq_key = get_groq_key()
    if not groq_key:
        return None, "Key not found"

    system_text, turns = normalize_messages(messages)
    clean_messages = []
    if system_text:
        clean_messages.append({"role": "system", "content": system_text})
    clean_messages.extend(turns)

    headers = {
        "Authorization": f"Bearer {groq_key}",
        "Content-Type": "application/json"
    }
    timeout = aiohttp.ClientTimeout(total=20)
    last_err = "Unknown error"

    for model in GROQ_MODELS:
        payload = {
            "model": model,
            "messages": clean_messages,
            "max_tokens": max_tokens,
            "temperature": temperature
        }
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(GROQ_URL, headers=headers, json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data["choices"][0]["message"]["content"].strip(), None
                    else:
                        err_body = await response.text()
                        last_err = f"HTTP {response.status}: {err_body[:100]}"
                        logger.error(f"Groq API error ({model}) HTTP {response.status}: {err_body}")
        except Exception as e:
            last_err = str(e)
            logger.error(f"Groq API request exception ({model}): {e}")

    return None, last_err


async def _call_ai(messages: list, max_tokens: int = 500, temperature: float = 0.8) -> str:
    """
    Главная точка входа в AI.
    1. Пробует Google Gemini (1 000 000 TPM бесплатно).
    2. При ошибке или отсутствии ключа — переключается на Groq (Llama).
    """
    if get_gemini_key():
        res, _ = await _call_gemini_native(messages, max_tokens, temperature)
        if res:
            return res

    if get_groq_key():
        res, _ = await _call_groq(messages, max_tokens, temperature)
        if res:
            return res

    return None


async def test_ai_connection() -> dict:
    """Диагностическая функция для детальной проверки статуса AI провайдеров."""
    gemini_key = get_gemini_key()
    groq_key = get_groq_key()

    results = {
        "gemini_key_present": bool(gemini_key),
        "groq_key_present": bool(groq_key),
        "gemini_status": "Not configured",
        "groq_status": "Not configured",
        "gemini_key_mask": f"{gemini_key[:6]}...{gemini_key[-4:]}" if len(gemini_key) > 10 else ("Set" if gemini_key else "Missing"),
        "groq_key_mask": f"{groq_key[:6]}...{groq_key[-4:]}" if len(groq_key) > 10 else ("Set" if groq_key else "Missing"),
    }

    test_messages = [{"role": "user", "content": "Привет! Ответь одним словом: Работает"}]

    if gemini_key:
        res, err = await _call_gemini_native(test_messages, max_tokens=10)
        results["gemini_status"] = f"✅ OK ({res})" if res else f"❌ {err}"

    if groq_key:
        res, err = await _call_groq(test_messages, max_tokens=10)
        results["groq_status"] = f"✅ OK ({res})" if res else f"❌ {err}"

    return results


async def get_ai_explanation(test_name: str, score: int, level: str, lang: str = "ru") -> str:
    cache_key = f"{test_name}:{score}:{level}:{lang}"
    if cache_key in _TEST_EXPLANATION_CACHE:
        return _TEST_EXPLANATION_CACHE[cache_key]

    if not get_groq_key() and not get_gemini_key():
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
    if not get_groq_key() and not get_gemini_key():
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
