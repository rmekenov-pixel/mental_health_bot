from aiogram import Router, F
from aiogram.types import Message, BufferedInputFile
from bot.services.charts import generate_chart
from bot.keyboards.test_kb import get_main_keyboard

router = Router()


@router.message(F.text == "📈 График")
async def show_chart(message: Message):
    await message.answer("📈 Генерирую график...")

    buf = await generate_chart(message.from_user.id)

    if buf is None:
        await message.answer(
            "📭 Недостаточно данных для графика.\n\n"
            "Пройди тест или сделай чек-ин — и данные появятся!",
            reply_markup=get_main_keyboard()
        )
        return

    photo = BufferedInputFile(buf.read(), filename="chart.png")
    await message.answer_photo(
        photo=photo,
        caption="📊 Твоя динамика за последние 7 дней",
        reply_markup=get_main_keyboard()
    )