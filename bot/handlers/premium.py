"""
Модуль монетизации и управления платной подпиской MindCheck Pro.
Реализует нативную оплату через Telegram Stars (валюта XTR, без внешних эквайрингов),
выдачу подписки, продление, админ-управление и проверку статуса.
"""

import logging
from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    LabeledPrice,
    PreCheckoutQuery,
)
from aiogram.filters import Command
from database.db import AsyncSessionLocal
from database.models import User
from sqlalchemy import select
from bot.services.localization import get_user_lang, t
from bot.config import ADMIN_ID

logger = logging.getLogger("premium_handler")
router = Router()

# Конфигурация тарифов в Telegram Stars (XTR)
# 1 Telegram Star ≈ $0.02 USD (150 Stars ≈ $3.00)
TARIFFS = {
    "1m": {
        "days": 30,
        "stars": 150,
        "label_ru": "⭐ 1 месяц (150 ⭐️)",
        "label_kz": "⭐ 1 ай (150 ⭐️)",
        "label_en": "⭐ 1 month (150 ⭐️)",
        "title_ru": "MindCheck Pro — 1 месяц",
        "title_kz": "MindCheck Pro — 1 ай",
        "title_en": "MindCheck Pro — 1 month",
        "desc_ru": "30 дней безлимитного AI-чата, глубоких инсайтов и персонального коучинга",
        "desc_kz": "30 күн шектеусіз AI-чат, терең инсайттар және жеке коучинг",
        "desc_en": "30 days of unlimited AI chat, deep insights and personal coaching",
    },
    "3m": {
        "days": 90,
        "stars": 390,
        "label_ru": "🔥 3 месяца (390 ⭐️) — Скидка 15%",
        "label_kz": "🔥 3 ай (390 ⭐️) — 15% жеңілдік",
        "label_en": "🔥 3 months (390 ⭐️) — Save 15%",
        "title_ru": "MindCheck Pro — 3 месяца",
        "title_kz": "MindCheck Pro — 3 ай",
        "title_en": "MindCheck Pro — 3 months",
        "desc_ru": "90 дней заботы о ментальном здоровье с выгодой 15%",
        "desc_kz": "15% жеңілдікпен 90 күндік толық мүмкіндіктер",
        "desc_en": "90 days of complete mental wellbeing with 15% discount",
    },
    "1y": {
        "days": 365,
        "stars": 1190,
        "label_ru": "👑 1 год (1190 ⭐️) — Скидка 35%",
        "label_kz": "👑 1 жыл (1190 ⭐️) — 35% жеңілдік",
        "label_en": "👑 1 year (1190 ⭐️) — Save 35%",
        "title_ru": "MindCheck Pro — 1 год",
        "title_kz": "MindCheck Pro — 1 жыл",
        "title_en": "MindCheck Pro — 1 year",
        "desc_ru": "365 дней максимальной поддержки с выгодой 35%",
        "desc_kz": "35% жеңілдікпен 1 жылдық толық қолдау",
        "desc_en": "365 days of maximum support with 35% discount",
    },
}


def get_premium_menu_keyboard(lang: str = "ru", is_active: bool = False) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=TARIFFS["1m"][f"label_{lang}"], callback_data="buy_stars_1m")],
        [InlineKeyboardButton(text=TARIFFS["3m"][f"label_{lang}"], callback_data="buy_stars_3m")],
        [InlineKeyboardButton(text=TARIFFS["1y"][f"label_{lang}"], callback_data="buy_stars_1y")],
    ]
    if is_active:
        status_btn_text = "✨ Проверить статус подписки" if lang == "ru" else ("✨ Жазылым күйін тексеру" if lang == "kz" else "✨ Check status")
        buttons.append([InlineKeyboardButton(text=status_btn_text, callback_data="check_my_premium")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(Command("premium"))
async def cmd_premium(message: Message):
    lang = await get_user_lang(message.from_user.id)
    telegram_id = message.from_user.id

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()

    is_premium = False
    premium_text_status = ""
    now = datetime.utcnow()

    if user and user.is_premium:
        if user.premium_until and user.premium_until > now:
            is_premium = True
            days_left = (user.premium_until - now).days
            date_str = user.premium_until.strftime("%d.%m.%Y")
            premium_text_status = f"\n\n⭐ <b>Ваша подписка активна:</b> до <b>{date_str}</b> (осталось {days_left} дн.)\n"
        elif not user.premium_until:
            is_premium = True
            premium_text_status = "\n\n⭐ <b>Ваша подписка:</b> Навсегда (Unlimited Lifetime)\n"

    title_ru = (
        "👑 <b>Премиум подписка MindCheck Pro</b>"
        f"{premium_text_status}\n"
        "Открой полный потенциал доказательного психологического ассистента:\n\n"
        "🚀 <b>Преимущества MindCheck Pro:</b>\n"
        "• <b>Безлимитный AI-чат</b> (до 150 глубоких ответов в день)\n"
        "• <b>Флагманские модели</b> (GPT-OSS 120B & LLaMA 3.3 70B)\n"
        "• <b>Глубокие инсайты</b> (анализ связей сна, настроения и тревоги за 30 дней)\n"
        "• <b>Персональный воскресный AI-коучинг</b>\n"
        "• <b>Приоритетная скорость</b> ответов без задержек\n\n"
        "💳 <i>Оплата осуществляется безопасно внутренней валютой Telegram Stars (⭐️) в 1 клик.</i>\n\n"
        "<b>Выберите подходящий тариф:</b>"
    )
    title_kz = (
        "👑 <b>MindCheck Pro премиум жазылымы</b>"
        f"{premium_text_status}\n"
        "Психологиялық ассистенттің барлық мүмкіндіктерін ашыңыз:\n\n"
        "🚀 <b>MindCheck Pro артықшылықтары:</b>\n"
        "• <b>Шектеусіз AI-чат</b> (күніне 150-ге дейін терең жауап)\n"
        "• <b>Флагмандық модельдер</b> (GPT-OSS 120B & LLaMA 3.3 70B)\n"
        "• <b>Терең инсайттар</b> (30 күндік ұйқы, көңіл-күй және мазасыздық талдауы)\n"
        "• <b>Жексенбілік жеке AI-коучинг</b>\n"
        "• <b>Жылдам жауаптар</b> кезексіз\n\n"
        "💳 <i>Төлем Telegram Stars (⭐️) арқылы 1 басумен қауіпсіз орындалады.</i>\n\n"
        "<b>Өзіңізге ыңғайлы тарифті таңдаңыз:</b>"
    )
    title_en = (
        "👑 <b>MindCheck Pro Premium</b>"
        f"{premium_text_status}\n"
        "Unlock the full power of your evidence-based mental wellbeing companion:\n\n"
        "🚀 <b>MindCheck Pro Benefits:</b>\n"
        "• <b>Unlimited AI Conversations</b> (up to 150 daily responses)\n"
        "• <b>Flagship LLM Models</b> (GPT-OSS 120B & LLaMA 3.3 70B)\n"
        "• <b>Deep Insights</b> (30-day cross-correlation of sleep, mood & anxiety)\n"
        "• <b>Weekly Personalized AI Coaching</b>\n"
        "• <b>Instant Priority Responses</b>\n\n"
        "💳 <i>Paid safely with 1-click native Telegram Stars (⭐️).</i>\n\n"
        "<b>Choose your plan:</b>"
    )

    msg_map = {"ru": title_ru, "kz": title_kz, "en": title_en}
    text = msg_map.get(lang, title_ru)

    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=get_premium_menu_keyboard(lang, is_active=is_premium)
    )


@router.callback_query(F.data.startswith("buy_stars_"))
async def process_buy_stars(callback: CallbackQuery):
    tariff_key = callback.data.replace("buy_stars_", "")
    if tariff_key not in TARIFFS:
        await callback.answer("Тариф не найден", show_alert=True)
        return

    lang = await get_user_lang(callback.from_user.id)
    t_info = TARIFFS[tariff_key]

    prices = [LabeledPrice(label=t_info[f"title_{lang}"], amount=t_info["stars"])]

    await callback.bot.send_invoice(
        chat_id=callback.from_user.id,
        title=t_info[f"title_{lang}"],
        description=t_info[f"desc_{lang}"],
        payload=f"sub_{tariff_key}",
        provider_token="",  # Для Telegram Stars provider_token всегда пустой
        currency="XTR",
        prices=prices,
        start_parameter=f"mindcheck_pro_{tariff_key}",
    )
    await callback.answer()


@router.pre_checkout_query()
async def pre_checkout_handler(pre_checkout: PreCheckoutQuery):
    """Обязательное подтверждение готовности принять платёж Telegram."""
    await pre_checkout.answer(ok=True)


@router.message(F.successful_payment)
async def successful_payment_handler(message: Message):
    """Обработка успешной оплаты Telegram Stars и активация подписки."""
    sp = message.successful_payment
    payload = sp.invoice_payload
    telegram_id = message.from_user.id
    lang = await get_user_lang(telegram_id)

    days_to_add = 30
    if payload == "sub_3m":
        days_to_add = 90
    elif payload == "sub_1y":
        days_to_add = 365

    now = datetime.utcnow()

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()

        if user:
            user.is_premium = True
            current_until = user.premium_until
            if current_until and current_until > now:
                user.premium_until = current_until + timedelta(days=days_to_add)
            else:
                user.premium_until = now + timedelta(days=days_to_add)
            await session.commit()
            new_date = user.premium_until.strftime("%d.%m.%Y")
        else:
            new_date = (now + timedelta(days=days_to_add)).strftime("%d.%m.%Y")

    logger.info(f"Payment successful: user {telegram_id} paid {sp.total_amount} {sp.currency} for {payload}")

    success_ru = (
        f"🎉 <b>Поздравляем с подпиской MindCheck Pro!</b>\n\n"
        f"💳 Оплата <b>{sp.total_amount} ⭐️</b> успешно принята.\n"
        f"⭐ Премиум активен до <b>{new_date}</b>.\n\n"
        "Теперь вам доступны:\n"
        "• Безлимитный диалог с AI-ассистентом\n"
        "• Умные 30-дневные инсайты в меню 🔍 Инсайты\n"
        "• Персональный разбор динамики\n\n"
        "<i>Спасибо за доверие и заботу о своём эмоциональном здоровье!</i> 🙏"
    )
    success_kz = (
        f"🎉 <b>MindCheck Pro жазылымыңыз сәтті белсендірілді!</b>\n\n"
        f"💳 <b>{sp.total_amount} ⭐️</b> төлемі қабылданды.\n"
        f"⭐ Премиум мерзімі: <b>{new_date}</b> дейін.\n\n"
        "Барлық шектеусіз мүмкіндіктер қосылды!\n"
        "<i>Сенім артқаныңызға рақмет!</i> 🙏"
    )
    success_en = (
        f"🎉 <b>Welcome to MindCheck Pro!</b>\n\n"
        f"💳 Payment of <b>{sp.total_amount} ⭐️</b> received successfully.\n"
        f"⭐ Pro active until <b>{new_date}</b>.\n\n"
        "All unlimited AI capabilities & 30-day deep insights are now unlocked.\n"
        "<i>Thank you for supporting MindCheck!</i> 🙏"
    )

    msg_map = {"ru": success_ru, "kz": success_kz, "en": success_en}
    await message.answer(msg_map.get(lang, success_ru), parse_mode="HTML")


@router.callback_query(F.data == "check_my_premium")
async def check_my_premium_status(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    lang = await get_user_lang(telegram_id)

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()

    if user and user.is_premium and user.premium_until:
        now = datetime.utcnow()
        if user.premium_until > now:
            days = (user.premium_until - now).days
            date_str = user.premium_until.strftime("%d.%m.%Y")
            await callback.answer(f"⭐ MindCheck Pro активен до {date_str} (осталось {days} дн.)", show_alert=True)
            return

    await callback.answer("У вас пока нет активной Pro-подписки.", show_alert=True)


# --- АДМИНИСТРАТИВНЫЕ КОМАНДЫ ВЫДАЧИ ПОДПИСКИ ---

@router.message(Command("grant_premium"))
async def cmd_grant_premium(message: Message):
    """
    Выдача премиума вручную администратором:
    /grant_premium <telegram_id> [дней]
    """
    if message.from_user.id != ADMIN_ID:
        return

    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Формат: <code>/grant_premium &lt;telegram_id&gt; [дней, по умолчанию 30]</code>", parse_mode="HTML")
        return

    try:
        target_id = int(parts[1])
        days = int(parts[2]) if len(parts) > 2 else 30
    except ValueError:
        await message.answer("❌ ID и количество дней должны быть числами.")
        return

    now = datetime.utcnow()
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.telegram_id == target_id))
        user = result.scalar_one_or_none()

        if not user:
            user = User(telegram_id=target_id, is_premium=True, premium_until=now + timedelta(days=days))
            session.add(user)
        else:
            user.is_premium = True
            current_until = user.premium_until
            if current_until and current_until > now:
                user.premium_until = current_until + timedelta(days=days)
            else:
                user.premium_until = now + timedelta(days=days)

        await session.commit()
        until_date = user.premium_until.strftime("%d.%m.%Y")

    await message.answer(
        f"✅ Пользователю <code>{target_id}</code> успешно выдан <b>MindCheck Pro</b> на {days} дн. (до {until_date})",
        parse_mode="HTML"
    )

    try:
        await message.bot.send_message(
            target_id,
            f"🎁 <b>Вам активирован доступ MindCheck Pro на {days} дней!</b>\n\n"
            f"Срок действия: до <b>{until_date}</b>.\n"
            "Приятного использования! ⭐",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.warning(f"Could not notify user {target_id} about granted premium: {e}")


@router.message(Command("revoke_premium"))
async def cmd_revoke_premium(message: Message):
    """
    Отзыв премиума администратором:
    /revoke_premium <telegram_id>
    """
    if message.from_user.id != ADMIN_ID:
        return

    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Формат: <code>/revoke_premium &lt;telegram_id&gt;</code>", parse_mode="HTML")
        return

    try:
        target_id = int(parts[1])
    except ValueError:
        await message.answer("❌ ID должен быть числом.")
        return

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.telegram_id == target_id))
        user = result.scalar_one_or_none()
        if user:
            user.is_premium = False
            user.premium_until = None
            await session.commit()

    await message.answer(f"🚫 Премиум у пользователя <code>{target_id}</code> успешно аннулирован.", parse_mode="HTML")
