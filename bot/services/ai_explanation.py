import os
import aiohttp
import logging
import bot.config as cfg

logger = logging.getLogger("ai_explanation")

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODELS_URL = "https://api.groq.com/openai/v1/models"
GEMINI_OPENAI_URL = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"

def get_groq_key() -> str:
    # Динамический поиск ключа Groq
    for k in ["GROQ_API_KEY", "GROQ_KEY", "GROQ_TOKEN", "GROQ"]:
        val = os.environ.get(k)
        if val:
            return val.strip().strip('"').strip("'")
    for k, v in os.environ.items():
        if "groq" in k.lower() and v and len(v.strip()) > 10:
            return v.strip().strip('"').strip("'")
    return (cfg.GROQ_API_KEY or "").strip().strip('"').strip("'")

def get_gemini_key() -> str:
    # Динамический поиск ключа Gemini
    for k in ["GEMINI_API_KEY", "GOOGLE_API_KEY", "GEMINI_KEY", "GOOGLE_GEMINI_API_KEY", "GEMINI_TOKEN", "GEMINI", "GOOGLE_KEY"]:
        val = os.environ.get(k)
        if val:
            return val.strip().strip('"').strip("'")
    for k, v in os.environ.items():
        if ("gemini" in k.lower() or "google" in k.lower()) and v and len(v.strip()) > 10:
            return v.strip().strip('"').strip("'")
    return (cfg.GEMINI_API_KEY or "").strip().strip('"').strip("'")

_GROQ_ACTIVE_MODELS_CACHE = []
_TEST_EXPLANATION_CACHE = {}

# Приоритет выбора качественных флагманских моделей
MODEL_PRIORITY = [
    "openai/gpt-oss-120b",
    "llama-3.3-70b-versatile",
    "deepseek-r1-distill-llama-70b",
    "qwen/qwen3.6-27b",
    "qwen-2.5-32b",
    "openai/gpt-oss-20b",
    "llama-3.1-70b-versatile",
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
- Помочь человеку глубоко и понятно осознать результат теста простым, живым и поддерживающим языком
- Предложить 1-2 конкретные научно обоснованные практики (КПТ, майндфулнес, дыхательные упражнения, физиологические техники)
- Напомнить, что тест — это инструмент самонаблюдения, а не медицинский диагноз

Стиль:
- Пиши тепло, подробно, с заботой и эмпатией.
- Каждую технику объясняй пошагово: что делать, как дышать, сколько минут выполнять.
- Обязательно завершай все фразы и выводы до конца."""

SYSTEM_PROMPT_REFLECTION = """Ты MindCheck — чуткий, внимательный и умный ассистент по психологическому самонаблюдению.

Твоя роль:
- Проанализировать недельную динамику состояния человека (настроение, тревога, энергия, сон)
- Заметить неочевидные связи и паттерны в показателях
- Дать развёрнутые, тёплые и практически применимые рекомендации

Стиль:
- Живой человеческий язык, искренний интерес к благополучию пользователя.
- Конкретные пошаговые техники доказательной психологии.
- Всегда заканчивай мысль и сообщение логичным финалом."""


def normalize_messages(messages: list) -> tuple[str, list]:
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
                    
                    chat_only = [m for m in raw_ids if not any(x in m.lower() for x in ["whisper", "guard", "vision", "embed", "orpheus", "tts", "stt", "mixtral"])]

                    sorted_models = []
                    for preferred in MODEL_PRIORITY:
                        if preferred in chat_only:
                            sorted_models.append(preferred)
                    
                    for m_id in chat_only:
                        if m_id not in sorted_models:
                            sorted_models.append(m_id)

                    if sorted_models:
                        _GROQ_ACTIVE_MODELS_CACHE = sorted_models
                        logger.info(f"Groq chat models prioritized: {sorted_models[:4]}")
                        return sorted_models
    except Exception as e:
        logger.error(f"Failed to fetch live Groq models: {e}")

    return MODEL_PRIORITY


async def _call_gemini_native(messages: list, max_tokens: int = 2500, temperature: float = 0.6) -> tuple[str, str]:
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

    timeout = aiohttp.ClientTimeout(total=30)
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

    # Запасной OpenAI-совместимый эндпоинт
    openai_messages = []
    if system_text:
        openai_messages.append({"role": "system", "content": system_text})
    openai_messages.extend(turns)

    headers_openai = {
        "Authorization": f"Bearer {gemini_key}",
        "Content-Type": "application/json"
    }
    payload_openai = {
        "model": "gemini-1.5-flash",
        "messages": openai_messages,
        "max_tokens": max_tokens,
        "temperature": temperature
    }
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(GEMINI_OPENAI_URL, headers=headers_openai, json=payload_openai) as response:
                if response.status == 200:
                    data = await response.json()
                    return data["choices"][0]["message"]["content"].strip(), None
                else:
                    err_body = await response.text()
                    last_err = f"OpenAI-compat HTTP {response.status}: {err_body[:100]}"
    except Exception as e:
        last_err = str(e)

    return None, last_err


async def _call_groq(messages: list, max_tokens: int = 2500, temperature: float = 0.6) -> tuple[str, str]:
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
    timeout = aiohttp.ClientTimeout(total=30)
    last_err = "Unknown error"

    models_to_try = await _get_live_groq_models(groq_key)

    for model in models_to_try:
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
                        logger.warning(f"Groq model {model} returned HTTP {response.status}")
        except Exception as e:
            last_err = str(e)
            logger.warning(f"Groq model {model} failed: {e}")

    return None, last_err


async def _call_ai(messages: list, max_tokens: int = 2500, temperature: float = 0.6) -> str:
    """
    Главная точка входа в AI.
    Большой лимит токенов (2500) предотвращает обрезку длинных планов и анализов.
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

    # Собираем список всех переменных для наглядной диагностики Railway
    all_env_keys = sorted([k for k in os.environ.keys() if not k.startswith("_")])

    results = {
        "gemini_key_present": bool(gemini_key),
        "groq_key_present": bool(groq_key),
        "gemini_status": "Not configured",
        "groq_status": "Not configured",
        "gemini_key_mask": f"{gemini_key[:6]}...{gemini_key[-4:]}" if len(gemini_key) > 10 else ("Set" if gemini_key else "Missing"),
        "groq_key_mask": f"{groq_key[:6]}...{groq_key[-4:]}" if len(groq_key) > 10 else ("Set" if groq_key else "Missing"),
        "detected_env_names": ", ".join(all_env_keys[:12])
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

Напиши понятное, поддерживающее и полезное объяснение на грамотном {lang_name} языке:
1. Что означает этот результат простыми словами и почему не стоит паниковать
2. 2 конкретные научно доказанные практики с подробной инструкцией (как делать прямо сейчас)
3. Напоминание, что это самонаблюдение, а не диагноз"""

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT_EXPLANATION},
        {"role": "user", "content": prompt}
    ]

    result = await _call_ai(messages=messages, max_tokens=1500, temperature=0.6)
    if result:
        _TEST_EXPLANATION_CACHE[cache_key] = result
        return result

    return _FALLBACK_UNAVAILABLE_EXPLANATION.get(lang, _FALLBACK_UNAVAILABLE_EXPLANATION["ru"])


async def get_ai_weekly_reflection(avg_mood: float, avg_anxiety: float, avg_energy: float, checkin_count: int, lang: str = "ru") -> str:
    if not get_groq_key() and not get_gemini_key():
        return _FALLBACK_UNAVAILABLE_REFLECTION.get(lang, _FALLBACK_UNAVAILABLE_REFLECTION["ru"])

    lang_name = _LANG_NAMES.get(lang, _LANG_NAMES["ru"])

    prompt = f"""Пользователь отслеживал своё состояние {checkin_count} дней за неделю.
Средние показатели: настроение {avg_mood:.1f}/10, тревога {avg_anxiety:.1f}/10, энергия {avg_energy:.1f}/10.

Напиши тёплый, глубокий и полезный анализ недели на прекрасном {lang_name} языке:
1. Честный разбор этих показателей: что они значат и какие паттерны заметны
2. 2 точечные практики под его уровень энергии и тревоги с понятной инструкцией
3. Тёплые слова поддержки на предстоящую неделю"""

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT_REFLECTION},
        {"role": "user", "content": prompt}
    ]

    result = await _call_ai(messages=messages, max_tokens=1500, temperature=0.6)
    if result:
        return result

    return _FALLBACK_UNAVAILABLE_REFLECTION.get(lang, _FALLBACK_UNAVAILABLE_REFLECTION["ru"])
