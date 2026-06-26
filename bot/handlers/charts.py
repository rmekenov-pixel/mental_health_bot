from aiogram import Router, F
from aiogram.types import Message, BufferedInputFile
from bot.services.charts import generate_chart
from bot.keyboards.test_kb import get_main_keyboard
from bot.services.localization import t, get_user_lang

router = Router()


@router.message(F.text.in_({t(lang, "btn_chart") for lang in ("ru", "kz", "en")}))
async def show_chart(message: Message):
    lang = await get_user_lang(message.from_user.id)
    await message.answer(t(lang, "chart_generating"))

    buf = await generate_chart(message.from_user.id, lang)

    if buf is None:
        await message.answer(
            t(lang, "no_chart"),
            reply_markup=get_main_keyboard(lang)
        )
        return

    photo = BufferedInputFile(buf.read(), filename="chart.png")
    await message.answer_photo(
        photo=photo,
        caption=t(lang, "chart_caption"),
        reply_markup=get_main_keyboard(lang)
    )
