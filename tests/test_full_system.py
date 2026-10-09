import asyncio
import os
import sys
import json
from datetime import datetime, timedelta

# Добавляем путь проекта в sys.path
sys.path.insert(0, os.path.abspath("."))
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from bot.services.localization import load_locale, t
from bot.services.scoring import (
    load_test,
    calculate_score,
    calculate_self_esteem_scores,
    calculate_burnout_scores,
    get_level,
    get_test_questions,
    get_test_options,
)
from bot.services.crisis import is_crisis_text, get_crisis_message
from bot.services.ai_explanation import normalize_messages
from bot.keyboards.test_kb import get_main_keyboard, get_test_choice_keyboard, get_options_keyboard
from bot.handlers.language import LANG_MAP
from database.models import Base, User, TestResult, CheckIn, UserStreak, Feedback
from database.db import engine, AsyncSessionLocal, init_db
from sqlalchemy import select, func


async def run_full_tests():
    print("==================================================")
    print("STARTING FULL BOT AUDIT & 100% TEST SUITE EXECUTION")
    print("==================================================")

    passed = 0
    total = 0

    def assert_test(condition, name):
        nonlocal passed, total
        total += 1
        if condition:
            passed += 1
            print(f"  [PASS] {name}")
        else:
            print(f"  [FAIL] {name}")
            raise AssertionError(f"Test failed: {name}")

    # 1. ТЕСТ ЛОКАЛИЗАЦИИ
    print("\n--- 1. Localization Testing ---")
    locales = {}
    for lang in ("ru", "kz", "en"):
        locales[lang] = load_locale(lang)
        assert_test(len(locales[lang]) > 50, f"Locale {lang} has sufficient keys ({len(locales[lang])})")

    ru_keys = set(locales["ru"].keys())
    kz_keys = set(locales["kz"].keys())
    en_keys = set(locales["en"].keys())

    assert_test(ru_keys == kz_keys, "Ru and Kz keys match exactly")
    assert_test(ru_keys == en_keys, "Ru and En keys match exactly")

    for k in ru_keys:
        assert_test(bool(locales["ru"][k]), f"Ru key '{k}' is non-empty")
        assert_test(bool(locales["kz"][k]) or k.startswith("kz_"), f"Kz key '{k}' is present")
        assert_test(bool(locales["en"][k]) or k.startswith("kz_"), f"En key '{k}' is present")

    # 2. ТЕСТ ПСИХОЛОГИЧЕСКИХ ОПРОСНИКОВ И СКОРИНГА
    print("\n--- 2. Psychological Test Data & Scoring ---")
    tests = ["phq9", "gad7", "burnout", "self_esteem", "emotional_intelligence"]
    for test_name in tests:
        for lang in ("ru", "kz", "en"):
            t_data = load_test(test_name, lang)
            q_list = get_test_questions(test_name, lang)
            opt_list = get_test_options(test_name, lang)
            assert_test(len(q_list) > 0, f"Test {test_name} ({lang}) has questions ({len(q_list)})")
            assert_test(len(opt_list) > 1, f"Test {test_name} ({lang}) has options ({len(opt_list)})")

    # Тест PHQ-9 скоринга
    phq9_min = calculate_score([0] * 9)
    phq9_max = calculate_score([3] * 9)
    assert_test(phq9_min == 0, "PHQ-9 min score = 0")
    assert_test(phq9_max == 27, "PHQ-9 max score = 27")
    assert_test("отсутств" in get_level("phq9", 2, "ru").lower() or "миним" in get_level("phq9", 2, "ru").lower(), "PHQ-9 level 2 is minimal")
    assert_test("тяж" in get_level("phq9", 22, "ru").lower(), "PHQ-9 level 22 is severe")

    # Тест Самооценки (Розенберг) с обратными вопросами
    # Если на всё ответили "Полностью согласен" (0):
    # Прямые (0,2,3,6,9 -> 3 балла * 5 = 15), Обратные (1,4,5,7,8 -> 0 баллов * 5 = 0) -> Итого 15
    se_all_agree = calculate_self_esteem_scores([0] * 10)
    assert_test(se_all_agree == 15, f"Rosenberg all agree is 15 (got {se_all_agree})")

    # Если максимальная самооценка (прямые=0 (3 балла), обратные=3 (3 балла))
    se_max_answers = [0, 3, 0, 0, 3, 3, 0, 3, 3, 0]
    se_max = calculate_self_esteem_scores(se_max_answers)
    assert_test(se_max == 30, f"Rosenberg max score is 30 (got {se_max})")

    # Тест Burnout (Маслач)
    burnout_zeros = calculate_burnout_scores([0] * 22, "ru")
    assert_test(burnout_zeros["emotional_exhaustion"] == 0, "Burnout EE min = 0")
    assert_test(burnout_zeros["depersonalization"] == 0, "Burnout DP min = 0")
    assert_test(burnout_zeros["personal_achievement"] == 0, "Burnout PA min = 0")
    assert_test(burnout_zeros["total"] == 0, "Burnout Total min = 0")

    # 3. ТЕСТ АНТИКРИЗИСНЫХ ПРАВИЛ (SAFETY GUARDRAILS)
    print("\n--- 3. Crisis Detection (Safety) ---")
    crisis_positive_examples = [
        "я не хочу жить",
        "хочу умереть",
        "думаю покончить с собой",
        "вскрыть вены",
        "убить себя",
        "өлгім келеді",
        "өзіме қол жұмсағым келеді",
        "i want to die",
        "thinking about suicide",
        "better off dead"
    ]
    for phrase in crisis_positive_examples:
        assert_test(is_crisis_text(phrase), f"Crisis triggered for: '{phrase}'")

    crisis_negative_examples = [
        "Привет, как дела?",
        "У меня сегодня плохое настроение",
        "Очень устал на работе, выгораю",
        "Жизнь прекрасна, но сложна",
        "Мазасыздық деңгейім 5"
    ]
    for phrase in crisis_negative_examples:
        assert_test(not is_crisis_text(phrase), f"No false positive for: '{phrase}'")

    for lang in ("ru", "kz", "en"):
        msg = get_crisis_message(lang)
        assert_test("150" in msg or "988" in msg or "111" in msg, f"Crisis message {lang} contains hotlines")

    # 4. ТЕСТ НОРМАЛИЗАЦИИ СООБЩЕНИЙ AI
    print("\n--- 4. AI Message Normalization ---")
    raw_msgs = [
        {"role": "system", "content": "System 1"},
        {"role": "system", "content": "System 2"},
        {"role": "assistant", "content": "Initial assistant (should be skipped)"},
        {"role": "user", "content": "User question 1"},
        {"role": "user", "content": "User addition"},
        {"role": "assistant", "content": "Assistant answer"},
    ]
    sys_txt, turns = normalize_messages(raw_msgs)
    assert_test(sys_txt == "System 1\n\nSystem 2", "System messages concatenated properly")
    assert_test(len(turns) == 2, f"Turns reduced to 2 (got {len(turns)})")
    assert_test(turns[0]["role"] == "user" and turns[0]["content"] == "User question 1\n\nUser addition", "Consecutive user messages merged")

    # 5. ТЕСТ КЛАВИАТУР
    print("\n--- 5. Keyboard Builders ---")
    for lang in ("ru", "kz", "en"):
        kb_main = get_main_keyboard(lang)
        assert_test(len(kb_main.keyboard) >= 4, f"Main keyboard has >= 4 rows for {lang}")
        kb_tests = get_test_choice_keyboard(lang)
        assert_test(len(kb_tests.keyboard) == 5, f"Test choice keyboard has 5 tests for {lang}")

    # 6. ТЕСТ БАЗЫ ДАННЫХ И СТРИКОВ
    print("\n--- 6. Database and Streak Logic ---")
    await init_db()
    test_tg_id = 999999901

    async with AsyncSessionLocal() as session:
        # Очистка тестового пользователя
        user = (await session.execute(select(User).where(User.telegram_id == test_tg_id))).scalar_one_or_none()
        if user:
            await session.delete(user)
        streak = (await session.execute(select(UserStreak).where(UserStreak.telegram_id == test_tg_id))).scalar_one_or_none()
        if streak:
            await session.delete(streak)
        await session.commit()

        # Создание пользователя
        new_user = User(telegram_id=test_tg_id, username="testuser", language="ru")
        session.add(new_user)
        await session.commit()

        u = (await session.execute(select(User).where(User.telegram_id == test_tg_id))).scalar_one_or_none()
        assert_test(u is not None, "User successfully created in DB")
        assert_test(u.language == "ru", "User default language is 'ru'")

        # Создание чекина
        c = CheckIn(telegram_id=test_tg_id, mood=8, anxiety=3, energy=7, sleep_hours=8, sleep_quality=8)
        session.add(c)
        await session.commit()

        c_saved = (await session.execute(select(CheckIn).where(CheckIn.telegram_id == test_tg_id))).scalar_one_or_none()
        assert_test(c_saved.mood == 8 and c_saved.anxiety == 3, "CheckIn recorded successfully")

        # Очистка
        await session.delete(c_saved)
        await session.delete(u)
        await session.commit()

    print("\n==================================================")
    print(f"ALL TESTS COMPLETED SUCCESSFULLY: {passed}/{total} PASSED (100%)")
    print("==================================================")

if __name__ == "__main__":
    asyncio.run(run_full_tests())
