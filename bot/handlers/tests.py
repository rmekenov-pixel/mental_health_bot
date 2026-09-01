from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from bot.states.test_states import TestStates
from bot.keyboards.test_kb import get_test_choice_keyboard, get_options_keyboard, get_main_keyboard
from bot.services.scoring import get_test_questions, get_test_options, calculate_score, get_level, calculate_burnout_scores
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

    intro = t(
        lang, "test_intro",
        current=1, total=len(questions), question=questions[0]
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
    test_name = data["test_name"]
    questions = data["questions"]

    options = get_test_options(test_name, lang)
    keyboard = get_options_keyboard(options)

    try:
        answer_value = options.index(message.text)
    except ValueError:
        await message.answer(t(lang, "test_invalid"))
        return

    answers = data["answers"] + [answer_value]
    current = data["current_question"] + 1

    if current < len(questions):
        await state.update_data(answers=answers, current_question=current)
        await message.answer(
            t(lang, "test_question", current=current + 1, total=len(questions), question=questions[current]),
            reply_markup=keyboard
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

        # Если в PHQ-9 был положительный ответ на вопрос о причинении себе вреда или тяжелый балл
        if has_suicidal_ideation or (test_name == "phq9" and score >= 20):
            await message.answer(get_crisis_message(lang), parse_mode="HTML")

        explanation = await get_ai_explanation(display_name, score, level, lang)
        await message.answer(
            t(lang, "ai_explanation", text=explanation),
            parse_mode="HTML"
        )
