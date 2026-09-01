from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from bot.states.test_states import TestStates
from bot.keyboards.test_kb import get_test_choice_keyboard, get_options_keyboard, get_main_keyboard
from bot.services.scoring import (
    get_test_questions,
    get_test_options,
    calculate_score,
    calculate_self_esteem_scores,
    get_level,
    calculate_burnout_scores
)
from bot.services.ai_explanation import get_ai_explanation
from bot.services.localization import t, get_user_lang
from bot.services.crisis import get_crisis_message
from database.db import AsyncSessionLocal
from database.models import TestResult


router = Router()

_TEST_BTN_KEYS = {
    "test_btn_phq9": "phq9",
    "test_btn_gad7": "gad7",
    "test_btn_burnout": "burnout",
    "test_btn_self_esteem": "self_esteem",
    "test_btn_eq": "emotional_intelligence",
}


def _build_test_map() -> dict:
    from bot.services.localization import load_locale
    test_map = {}
    for lang in ("ru", "kz", "en"):
        locale = load_locale(lang)
        for btn_key, test_key in _TEST_BTN_KEYS.items():
            if btn_key in locale:
                test_map[locale[btn_key]] = test_key
    return test_map


TEST_MAP = _build_test_map()

TEST_DISPLAY_NAMES = {
    "phq9": "PHQ-9",
    "gad7": "GAD-7",
    "burnout": "BURNOUT",
    "self_esteem": "SELF-ESTEEM",
    "emotional_intelligence": "EQ",
}


def _format_question_text(lang: str, current: int, total: int, question: str, options: list[str]) -> str:
    """Форматирует текст вопроса вместе с пронумерованными вариантами ответа."""
    opt_lines = "\n".join(f"  <b>{i+1}.</b> {opt}" for i, opt in enumerate(options))
    return (
        f"❓ <b>Вопрос {current} из {total}:</b>\n\n"
        f"<i>{question}</i>\n\n"
        f"<b>Варианты ответа (выбери кнопку внизу или отправь цифру 1-{len(options)}):</b>\n{opt_lines}"
    )


@router.message(F.text.in_({t(lang, "btn_test") for lang in ("ru", "kz", "en")}))
async def choose_test(message: Message, state: FSMContext):
    lang = await get_user_lang(message.from_user.id)
    await state.clear()
    await state.set_state(TestStates.choosing_test)
    await message.answer(
        t(lang, "choose_test"),
        reply_markup=get_test_choice_keyboard(lang)
    )


@router.message(TestStates.choosing_test)
async def start_test(message: Message, state: FSMContext):
    lang = await get_user_lang(message.from_user.id)
    test_key = TEST_MAP.get(message.text)
    if not test_key:
        await message.answer(t(lang, "choose_test_invalid"))
        return

    questions = get_test_questions(test_key, lang)
    options = get_test_options(test_key, lang)
    await state.update_data(
        test_name=test_key,
        questions=questions,
        current_question=0,
        answers=[]
    )
    await state.set_state(TestStates.answering)

    keyboard = get_options_keyboard(options)

    intro = (
        f"📋 <b>Оцени своё состояние за последние 2 недели.</b>\n\n" +
        _format_question_text(lang, 1, len(questions), questions[0], options)
    )
    if lang == "kz":
        intro = t(lang, "kz_validation_disclaimer_intro") + intro

    await message.answer(
        intro,
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@router.message(TestStates.answering)
async def process_answer(message: Message, state: FSMContext):
    lang = await get_user_lang(message.from_user.id)
    data = await state.get_data()
    test_name = data.get("test_name")
    questions = data.get("questions")

    if not test_name or not questions:
        await state.clear()
        await message.answer("Сессия теста завершена. Нажмите «Пройти тест» для начала.", reply_markup=get_main_keyboard(lang))
        return

    options = get_test_options(test_name, lang)
    keyboard = get_options_keyboard(options)

    # Умный разбор ответа (поддержка кнопок, цифр 1..N, цифр в скобках, частичного текста)
    matched_idx = None
    user_text = message.text.strip()

    # 1. Точное совпадение с кнопкой
    if user_text in options:
        matched_idx = options.index(user_text)

    # 2. Ввод цифры (например '1', '2', '3', '4' или '0', '1', '2', '3')
    elif user_text.isdigit():
        num = int(user_text)
        # Если ввели порядковый номер (1..N)
        if 1 <= num <= len(options):
            matched_idx = num - 1
        # Если ввели балл (0..N-1)
        elif 0 <= num < len(options):
            # Ищем опцию, где в скобках указан этот балл
            for idx, opt in enumerate(options):
                if f"({num})" in opt:
                    matched_idx = idx
                    break
            if matched_idx is None:
                matched_idx = num

    # 3. Ввод частичного текста (например "полностью согласен" или "не согласен")
    if matched_idx is None:
        user_lower = user_text.lower()
        for idx, opt in enumerate(options):
            opt_clean = opt.lower().split("(")[0].strip()
            if user_lower == opt_clean or user_lower in opt.lower():
                matched_idx = idx
                break

    if matched_idx is None:
        await message.answer(
            f"⚠️ Пожалуйста, выберите один из вариантов кнопками ниже или отправьте цифру от 1 до {len(options)}.",
            reply_markup=keyboard
        )
        return

    answers = data["answers"] + [matched_idx]
    current = data["current_question"] + 1

    if current < len(questions):
        await state.update_data(answers=answers, current_question=current)
        question_text = _format_question_text(lang, current + 1, len(questions), questions[current], options)
        await message.answer(
            question_text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        return

    display_name = TEST_DISPLAY_NAMES.get(test_name, test_name.upper())

    # Проверка на суицидальные маркеры (Вопрос 9 в тесте PHQ-9: index 8)
    has_suicidal_ideation = (test_name == "phq9" and len(answers) >= 9 and answers[8] > 0)

    if test_name == "burnout":
        burnout = calculate_burnout_scores(answers, lang)
        async with AsyncSessionLocal() as session:
            result = TestResult(
                telegram_id=message.from_user.id,
                test_name="BURNOUT",
                score=burnout["total"],
                level=f"ЭИ:{burnout['ee_level']} | ДП:{burnout['dp_level']} | ЛД:{burnout['pa_level']}"
            )
            session.add(result)
            await session.commit()

        await state.clear()

        done_text = t(
            lang, "burnout_done",
            ee=burnout["emotional_exhaustion"], ee_level=burnout["ee_level"],
            dp=burnout["depersonalization"], dp_level=burnout["dp_level"],
            pa=burnout["personal_achievement"], pa_level=burnout["pa_level"]
        )
        if lang == "kz":
            done_text += t(lang, "kz_validation_disclaimer_result")

        await message.answer(
            done_text,
            parse_mode="HTML",
            reply_markup=get_main_keyboard(lang)
        )
        explanation = await get_ai_explanation(
            display_name,
            burnout["total"],
            f"Истощение: {burnout['ee_level']}, Деперсонализация: {burnout['dp_level']}, Достижения: {burnout['pa_level']}",
            lang
        )
        await message.answer(
            t(lang, "ai_explanation", text=explanation),
            parse_mode="HTML"
        )
    else:
        if test_name == "self_esteem":
            score = calculate_self_esteem_scores(answers)
        else:
            score = calculate_score(answers)

        level = get_level(test_name, score, lang)

        async with AsyncSessionLocal() as session:
            result = TestResult(
                telegram_id=message.from_user.id,
                test_name=display_name,
                score=score,
                level=level
            )
            session.add(result)
            await session.commit()

        await state.clear()

        done_text = t(lang, "test_done", score=score, level=level)
        if lang == "kz":
            done_text += t(lang, "kz_validation_disclaimer_result")

        await message.answer(
            done_text,
            parse_mode="HTML",
            reply_markup=get_main_keyboard(lang)
        )

        if has_suicidal_ideation or (test_name == "phq9" and score >= 20):
            await message.answer(get_crisis_message(lang), parse_mode="HTML")

        explanation = await get_ai_explanation(display_name, score, level, lang)
        await message.answer(
            t(lang, "ai_explanation", text=explanation),
            parse_mode="HTML"
        )
