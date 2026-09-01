import aiohttp
import logging
import bot.config as cfg

logger = logging.getLogger("ai_explanation")

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODELS_URL = "https://api.groq.com/openai/v1/models"
GEMINI_OPENAI_URL = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"

def get_groq_key() -> str:
    key = cfg.GROQ_API_KEY or ""
    return key.strip().strip('"').strip("'")

def get_gemini_key() -> str:
    key = cfg.GEMINI_API_KEY or ""
    return key.strip().strip('"').strip("'")

_GROQ_ACTIVE_MODELS_CACHE = []
_TEST_EXPLANATION_CACHE = {}

# Приоритет выбора качественных моделей (70B/32B с отличным русским языком)
MODEL_PRIORITY = [
    "llama-3.3-70b-versatile",
    "deepseek-r1-distill-llama-70b",
    "llama-3.1-70b-versatile",
    "qwen-2.5-32b",
    "llama-3.1-8b-instant",
]

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

SYSTEM_PROMPT_EXPLANATION = """Ты MindCheck — профессиональный, тёплый и внимательный ассистент по психологическому самонаблюдению.

Твоя роль:
- Помочь человеку понять результат теста простым, грамотным и ясным языком
- Предложить 1-2 практические техники доказательной психологии (КПТ, майндфулнес, поведенческая активация)
- Поддержать и напомнить, что тест — это инструмент самонаблюдения, а не медицинский диагноз

Границы:
- Пиши на безупречно грамотном, естественном русском языке. Запрещены кальки, машинный перевод и выдуманные слова.
- Не ставь диагнозы и не назначай лечение.
- Говори коротко (3-5 предложений), тепло и по делу."""

SYSTEM_PROMPT_REFLECTION = """Ты MindCheck — профессиональный и внимательный ассистент по психологическому самонаблюдению.

Твоя роль:
- Грамотно и тепло проанализировать недельную динамику состояния человека (настроение, тревога, энергия, сон)
- Заметить реальные закономерности в цифрах
- Дать конкретные и практически применимые рекомендации (режим сна, дыхательные практики, управление стрессом)

Стиль:
- Безупречная грамматика, живой человеческий язык без штампов, клише и нелепых выражений.
- Чётко, структурировано (3-5 предложений), опираясь строго на факты."""


def normalize_messages(messages: list) -> tuple[str, list]:
    """Нормализует список сообщений и объединяет последовательные реплики одного автора."""
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

    while turns and turns[0]["role"] == "assistant":
        turns.pop(0)

    return system_text, turns


async def _get_live_groq_models(groq_key: str) -> list[str]:
    """Запрашивает актуальный список моделей у Groq и сортирует по качеству русского языка."""
    global _GROQ_ACTIVE_MODELS_CACHE
    if _GROQ_ACTIVE_MODELS_CACHE:
        return _GROQ_ACTIVE_MODELS_CACHE

    headers = {"Authorization": f"Bearer {groq_key}"}
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=8)) as session:
            async with session.get(GROQ_MODELS_URL, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    raw_ids = [m["id"] for m in data.get("data", []) if m.get("active", True)]
                    
                    # Сортируем: сначала проверенные 70B/32B модели
                    sorted_models = []
                    for preferred in MODEL_PRIORITY:
                        if preferred in raw_ids:
                            sorted_models.append(preferred)
                    
                    # Добавляем остальные чат-модели
                    for m_id in raw_ids:
                        if m_id not in sorted_models and not any(x in m_id for x in ["whisper", "guard", "vision", "embed", "mixtral"]):
                            sorted_models.append(m_id)

                    if sorted_models:
                        _GROQ_ACTIVE_MODELS_CACHE = sorted_models
                        logger.info(f"Groq models sorted by quality: {sorted_models[:4]}")
                        return sorted_models
    except Exception as e:
        logger.error(f"Failed to fetch live Groq models: {e}")

    return MODEL_PRIORITY


async def _call_gemini_native(messages: list, max_tokens: int = 500, temperature: float = 0.4) -> tuple[str, str]:
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

    headers_native = {
        "x-goog-api-key": gemini_key,
        "Content-Type": "application/json"
    }

    timeout = aiohttp.ClientTimeout(total=20)
    last_err = "Unknown error"

    for model in ["gemini-1.5-flash", "gemini-2.0-flash", "gemini-1.5-flash-latest"]:
        urls = [
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={gemini_key}"
        ]
        for url in urls:
            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(url, headers=headers_native, json=payload) as response:
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
            except Exception as e:
                last_err = str(e)

    return None, last_err


async def _call_groq(messages: list, max_tokens: int = 500, temperature: float = 0.4) -> tuple[str, str]:
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

    models_to_try = await _get_live_groq_models(groq_key)

    for model in models_to_try:
        payload = {
            "model": model,
            "messages": clean_messages,
            "max_tokens": max_tokens,
            "temperature": temperature  # Низкая температура 0.4 для идеальной грамматики
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
                        logger.warning(f"Groq model {model} returned HTTP {response.status}")
        except Exception as e:
            last_err = str(e)
            logger.warning(f"Groq model {model} failed: {e}")

    return None, last_err


async def _call_ai(messages: list, max_tokens: int = 500, temperature: float = 0.4) -> str:
    """
    Главная точка входа в AI.
    Использует умеренную температуру 0.4 для строгой связности и чистой грамматики.
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

    test_messages = [{"role": "user", "content": "Ответь одним словом: Работает"}]

    if gemini_key:
        res, err = await _call_gemini_native(test_messages, max_tokens=10, temperature=0.2)
        results["gemini_status"] = f"✅ OK ({res})" if res else f"❌ {err}"

    if groq_key:
        res, err = await _call_groq(test_messages, max_tokens=10, temperature=0.2)
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

Напиши понятное объяснение на чистом, грамотном {lang_name} языке (3-4 предложения):
1. Что означает этот результат простыми словами
2. 1-2 конкретные научно доказанные практики (КПТ, дыхание, режим)
3. Напоминание, что это самонаблюдение, а не диагноз"""

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT_EXPLANATION},
        {"role": "user", "content": prompt}
    ]

    result = await _call_ai(messages=messages, max_tokens=400, temperature=0.4)
    if result:
        _TEST_EXPLANATION_CACHE[cache_key] = result
        return result

    return _FALLBACK_UNAVAILABLE_EXPLANATION.get(lang, _FALLBACK_UNAVAILABLE_EXPLANATION["ru"])


async def get_ai_weekly_reflection(avg_mood: float, avg_anxiety: float, avg_energy: float, checkin_count: int, lang: str = "ru") -> str:
    if not get_groq_key() and not get_gemini_key():
        return _FALLBACK_UNAVAILABLE_REFLECTION.get(lang, _FALLBACK_UNAVAILABLE_REFLECTION["ru"])

    lang_name = _LANG_NAMES.get(lang, _LANG_NAMES["ru"])

    prompt = f"""Пользователь делал чек-ин {checkin_count} дней за неделю.
Средние показатели: настроение {avg_mood:.1f}/10, тревога {avg_anxiety:.1f}/10, энергия {avg_energy:.1f}/10.

Напиши анализ недели на безупречном {lang_name} языке (3-4 предложения):
1. Что означают эти показатели для состояния человека
2. На что обратить внимание и какую одну конкретную практику применить"""

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT_REFLECTION},
        {"role": "user", "content": prompt}
    ]

    result = await _call_ai(messages=messages, max_tokens=400, temperature=0.4)
    if result:
        return result

    return _FALLBACK_UNAVAILABLE_REFLECTION.get(lang, _FALLBACK_UNAVAILABLE_REFLECTION["ru"])
