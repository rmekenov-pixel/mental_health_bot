"""
Модуль экстренной психологической помощи и антикризисных правил (Safety Guardrails).
Перехватывает суицидальные намерения и критические состояния,
предоставляя контакты служб экстренной помощи без задержек и рассуждений AI.
"""

import re
from typing import Optional

# Регулярные выражения для поиска кризисных триггеров
_CRISIS_PATTERNS = [
    # Русский
    r"\b(не\s+хочу\s+жить|хочу\s+умереть|покончить\s+с\s+собой|покончу\s+с\s+собой)\b",
    r"\b(суицид|самоубийств\w*|вскрыть\s+вены|убить\s+себя|спрыгнуть\s+с\s+крыш\w*|повесить\w*)\b",
    r"\b(нет\s+смысла\s+жить|лучше\s+бы\s+я\s+умер\w*|не\s+могу\s+больше\s+жить)\b",
    # Казахский
    r"\b(өлгім\s+келеді|өзіме\s+қол\s+жұмса\w*|өмірден\s+шаршадым|өлгім\s+кеп\s+тұр)\b",
    r"\b(өмір\s+сүруден\s+мән\s+жоқ|өлу\s+туралы)\b",
    # Английский
    r"\b(want\s+to\s+die|kill\s+myself|end\s+my\s+life|suicid\w*|commit\s+suicide)\b",
    r"\b(don't\s+want\s+to\s+live|better\s+off\s+dead|no\s+reason\s+to\s+live)\b",
]

_COMPILED_CRISIS_REGEX = [re.compile(p, re.IGNORECASE) for p in _CRISIS_PATTERNS]

_CRISIS_MESSAGES = {
    "ru": (
        "🚨 <b>Пожалуйста, обрати внимание: тебе не нужно проходить через это в одиночку!</b>\n\n"
        "Если ты чувствуешь, что находишься в кризисном состоянии или у тебя возникают мысли о причинении себе вреда, "
        "пожалуйста, прямо сейчас обратись к специалистам, которые готовы помочь <b>бесплатно и анонимно</b>:\n\n"
        "🇰🇿 <b>Казахстан:</b>\n"
        "• <b>150</b> — Национальная линия доверия (круглосуточно, бесплатно)\n"
        "• <b>111</b> — Единый контакт-центр психологической помощи\n"
        "• <b>+7 (727) 376-56-60</b> — Горячая линия РНПЦПЗ\n\n"
        "🇷🇺 <b>Россия:</b>\n"
        "• <b>8-800-200-01-22</b> — Единый телефон доверия\n"
        "• <b>051</b> (с городского) или <b>+7 (495) 051</b> (с мобильного) — Неотложная психологическая помощь\n"
        "• <b>8-800-333-44-34</b> — Кризисная линия доверия\n\n"
        "🌍 <b>Другие страны:</b>\n"
        "• Международный каталог экстренной помощи: <a href='https://findahelpline.com'>findahelpline.com</a>\n\n"
        "<i>Я — лишь бот для самонаблюдения и не могу заменить живую профессиональную помощь. "
        "Пожалуйста, сделай этот шаг и свяжись со специалистом прямо сейчас. Твоя жизнь ценна!</i>"
    ),
    "kz": (
        "🚨 <b>Назар аударыңыз: бұл қиындықты жалғыз өткерудің қажеті жоқ!</b>\n\n"
        "Егер сіз өзіңізге зиян келтіру туралы ойласаңыз немесе ауыр дағдарыс жағдайында болсаңыз, "
        "дәл қазір <b>тегін және анонимді</b> көмек көрсететін мамандарға хабарласыңыз:\n\n"
        "🇰🇿 <b>Қазақстан:</b>\n"
        "• <b>150</b> — Ұлттық сенім телефоны (тәулік бойы, тегін)\n"
        "• <b>111</b> — Жедел психологиялық көмек байланыс орталығы\n"
        "• <b>+7 (727) 376-56-60</b> — РҒПК сенім телефоны\n\n"
        "🌍 <b>Басқа елдер үшін:</b> <a href='https://findahelpline.com'>findahelpline.com</a>\n\n"
        "<i>Бұл бот кәсіби дәрігер немесе психолог емес. Өтінеміз, маманның көмегіне жүгініңіз. Сіздің өміріңіз өте маңызды!</i>"
    ),
    "en": (
        "🚨 <b>Please read: You don't have to go through this alone!</b>\n\n"
        "If you are feeling overwhelmed, hopeless, or having thoughts of self-harm, "
        "please reach out to someone who can support you right now. These services are <b>free and confidential</b>:\n\n"
        "• <b>International Crisis Directories:</b>\n"
        "  - <a href='https://findahelpline.com'>findahelpline.com</a>\n"
        "  - <a href='https://www.befrienders.org'>befrienders.org</a>\n"
        "  - <a href='https://www.iasp.info/resources/Crisis_Centres/'>iasp.info Crisis Centers</a>\n\n"
        "• <b>US / Canada:</b> Call or text <b>988</b> (Suicide & Crisis Lifeline)\n"
        "• <b>UK:</b> Call <b>111</b> or text SHOUT to <b>85258</b>\n\n"
        "<i>I am only an automated self-tracking bot and cannot replace professional care. "
        "Please reach out to a professional or someone you trust right now. Your life matters!</i>"
    ),
}


def is_crisis_text(text: str) -> bool:
    """Проверяет, содержит ли текст пользователя маркеры суицидального кризиса."""
    if not text:
        return False
    text_clean = text.lower().strip()
    return any(pattern.search(text_clean) for pattern in _COMPILED_CRISIS_REGEX)


def get_crisis_message(lang: str = "ru") -> str:
    """Возвращает локализованное экстренное сообщение с контактами горячих линий."""
    return _CRISIS_MESSAGES.get(lang, _CRISIS_MESSAGES["ru"])
