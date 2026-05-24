from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from bot.states.test_states import TestStates
from bot.keyboards.test_kb import get_test_choice_keyboard, get_answer_keyboard, get_main_keyboard
from bot.services.scoring import get_test_questions, get_test_options, calculate_score, get_level
from database.db import AsyncSessionLocal
from database.models import TestResult
from bot.services.ai_explanation import get_ai_explanation

router = Router()

ANSWER_MAP = {
    "Совсем нет (0)": 0,
    "Несколько дней (1)": 1,
    "Больше половины дней (2)": 2,
    "Почти каждый день (3)": 3,
}

TEST_MAP = {
    "📋 PHQ-9 (Депрессия)": "phq9",
    "😰 GAD-7 (Тревожность)": "gad7",
}


@router.message(F.text == "🧪 Пройти тест")
async def choose_test(message: Message, state: FSMContext):
    await state.set_state(TestStates.choosing_test)
    await message.answer(
        "Выбери тест:",
        reply_markup=get_test_choice_keyboard()
    )


@router.message(TestStates.choosing_test)
async def start_test(message: Message, state: FSMContext):
    test_key = TEST_MAP.get(message.text)
    if not test_key:
        await message.answer("Пожалуйста, выбери тест из списка.")
        return

    questions = get_test_questions(test_key)
    await state.update_data(
        test_name=test_key,
        questions=questions,
        current_question=0,
        answers=[]
    )
    await state.set_state(TestStates.answering)
    await message.answer(
        f"❓ Вопрос 1 из {len(questions)}:\n\n{questions[0]}",
        reply_markup=get_answer_keyboard()
    )


@router.message(TestStates.answering)
async def process_answer(message: Message, state: FSMContext):
    answer_value = ANSWER_MAP.get(message.text)
    if answer_value is None:
        await message.answer("Пожалуйста, выбери один из вариантов ответа.")
        return

    data = await state.get_data()
    answers = data["answers"] + [answer_value]
    current = data["current_question"] + 1
    questions = data["questions"]
    test_name = data["test_name"]

    if current < len(questions):
        await state.update_data(answers=answers, current_question=current)
        await message.answer(
            f"❓ Вопрос {current + 1} из {len(questions)}:\n\n{questions[current]}",
            reply_markup=get_answer_keyboard()
        )
    else:
        score = calculate_score(answers)
        level = get_level(test_name, score)

        async with AsyncSessionLocal() as session:
            result = TestResult(
                telegram_id=message.from_user.id,
                test_name=test_name.upper(),
                score=score,
                level=level
            )
            session.add(result)
            await session.commit()

        await state.clear()
        await message.answer(
            f"✅ <b>Тест завершён!</b>\n\n"
            f"📊 Результат: <b>{score} баллов</b>\n"
            f"📝 Уровень: <b>{level}</b>\n\n"
            f"🤖 Получаю AI-объяснение...",
            parse_mode="HTML",
            reply_markup=get_main_keyboard()
        )

        explanation = await get_ai_explanation(test_name.upper(), score, level)
        await message.answer(
            f"💬 <b>AI-объяснение:</b>\n\n{explanation}\n\n"
            f"⚠️ Это не диагноз. Если вас беспокоит результат — обратитесь к специалисту.",
            parse_mode="HTML"
        )