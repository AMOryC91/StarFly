# FILE: handlers/shop.py
import logging
import os
import uuid
import hashlib
import time
from datetime import datetime, timedelta
from aiogram import Router, types, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import (
    BOT_USERNAME, REQUIRED_CHANNELS, STAR_RATE, MIN_STARS, SCREENSHOTS_DIR, OWNER_ID,
    REAL_TO_VIRTUAL_RATE, REAL_TO_VIRTUAL_MIN,
    VIRTUAL_TO_REAL_RATE, WITHDRAW_MIN_REAL,
    WITHDRAW_COMMISSION, EXCHANGE_COMMISSION, VIRTUAL_TO_REAL_COMMISSION,
    ROLE_NAMES, TICKET_GROUP_ID
)
from database import (
    get_user, update_balance, create_order, get_order_status, update_order_status,
    get_promocode, use_promocode, check_promocode_valid, get_user_orders,
    create_withdrawal, get_pending_withdrawals, update_withdrawal_status,
    create_exchange, get_user_active_discount, mark_discount_used,
    create_feedback, get_order_feedback, update_feedback_status,
    create_discount_link, use_discount_link,
    get_db_connection, log_admin_action, cancel_order, add_order_comment,
    get_user_by_referral_code, add_referral, set_referral_code, create_user,
    create_ticket, update_ticket_topic, get_ticket, get_ticket_by_topic_id,
    get_ticket_messages, add_ticket_message, get_user_tickets, get_all_tickets,
    update_ticket_status
)
from keyboards import (
    MenuCallback, OrderCallback, WithdrawalCallback, ExchangeCallback,
    FeedbackCallback, get_main_menu,
    get_back_to_menu_keyboard, get_skip_promocode_keyboard,
    get_order_action_keyboard, get_processed_order_keyboard,
    get_withdrawal_keyboard, get_exchange_approve_keyboard,
    get_feedback_order_keyboard, get_calculator_menu,
    get_exchange_menu, get_cancel_reasons_keyboard,
    get_skip_keyboard, get_rating_keyboard, get_support_keyboard,
    get_subscription_keyboard, get_ticket_action_keyboard, get_ticket_subjects_keyboard,
    SubjectCallback, TicketCallback
)
from states import (
    PurchaseStates, ExchangeStates, WithdrawalStates, CalculatorStates,
    TicketStates
)
from helpers import (
    get_screenshot_path, format_datetime, has_access,
    invalidate_balance_cache, invalidate_top_cache, is_duplicate_action,
    generate_referral_code, get_role_display
)

logger = logging.getLogger(__name__)

router = Router(name="shop")

# ========== КОМАНДЫ ИЗ utils.py ==========

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    logger.info(f"Команда /start от пользователя {message.from_user.id}")
    user_id = message.from_user.id
    username = message.from_user.username or ""
    full_name = message.from_user.full_name or f"User {user_id}"

    user = get_user(user_id)
    if not user:
        create_user(user_id, username, full_name)
        user = get_user(user_id)

    if user and not user[8]:
        referral_code = generate_referral_code(user_id)
        set_referral_code(user_id, referral_code)

    if len(message.text.split()) > 1:
        param = message.text.split()[1]

        if param.startswith('ref_'):
            ref_code = param[4:]
            referrer = get_user_by_referral_code(ref_code)
            if referrer and referrer[1] != user_id and user[9] is None:
                add_referral(referrer[1], user_id)

        elif param.startswith('discount_'):
            code = param.replace('discount_', '')
            discount, msg = use_discount_link(code, user_id)
            if discount:
                await message.answer(f"🎁 Вы получили скидку {discount}% на следующую покупку!")
            else:
                await message.answer(f"❌ {msg}")

        else:
            try:
                referrer_id = int(param)
                referrer = get_user(referrer_id)
                if referrer and referrer[1] != user_id and user[9] is None:
                    add_referral(referrer_id, user_id)
            except ValueError:
                pass

    welcome_text = (
        "🌟 <b>Добро пожаловать в StarFly Shop!</b> 🌟\n\n"
        "Здесь вы можете приобрести звёзды для Telegram аккаунтов.\n"
        f"Курс: <b>1 звезда = {STAR_RATE:.2f}₽</b>\n"
        f"Минимальная покупка: <b>{MIN_STARS} звёзд</b>"
    )
    await message.answer(welcome_text, reply_markup=get_main_menu())

@router.message(Command("help"))
async def cmd_help(message: types.Message):
    text = (
        "ℹ️ <b>Справка по боту</b>\n\n"
        "/start - Запустить бота\n"
        "/profile - Просмотр профиля\n"
        "/feedback - Оставить отзыв о покупке\n"
        "/support - Связаться с поддержкой\n"
        "/staff - Список администрации\n"
        "/info - Информация о боте\n"
        "/donate - Поддержать разработчика\n"
        "/report - Сообщить о проблеме (быстрый тикет)\n"
        "/help - Эта справка"
    )
    await message.answer(text, reply_markup=get_back_to_menu_keyboard())

@router.message(Command("info"))
async def cmd_info(message: types.Message):
    info_text = (
        "ℹ️ <b>Часто задаваемые вопросы</b>\n\n"
        "🌟 <b>Как происходит выдача товара?</b>\n"
        "Звёзды вы получаете прямо на указанный аккаунт.\n\n"
        "🌟 <b>Могу ли я покупать звёзды для других?</b>\n"
        "Да, нужно указать @username получателя.\n\n"
        "🌟 <b>Есть риск блокировки аккаунта?</b>\n"
        "Нет, мы используем официальные методы.\n\n"
        f"💰 <b>Курс:</b> 1 звезда = {STAR_RATE:.2f}₽\n"
        f"📦 <b>Минимальный заказ:</b> {MIN_STARS} звёзд\n\n"
    )
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🎁 Отправить подарок", url="https://t.me/XAP4KTEP"))
    kb.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=MenuCallback(action="back_to_menu").pack()))
    await message.answer(info_text, reply_markup=kb.as_markup())

@router.message(Command("donate"))
async def cmd_donate(message: types.Message):
    text = (
        "❤️ <b>Поддержать разработчика</b>\n\n"
        "Бот работает полностью бесплатно, но требует времени и ресурсов.\n"
        "Если вам нравится проект и вы хотите сказать спасибо:\n\n"
        "👤 <b>@XAP4KTEP</b> — создатель бота\n\n"
        "📤 <b>Способы поддержки:</b>\n"
        "• 🎁 Отправить подарок в Telegram\n"
        "• 💎 USDT (TON): <code>UQC9S7ejryrWTrVVc40qJjT0WTAUmFNhmDFOn6dlbHGjc6wm</code>\n"
        "• ⚡ TON: <code>UQC9S7ejryrWTrVVc40qJjT0WTAUmFNhmDFOn6dlbHGjc6wm</code>\n\n"
        "✨ Даже небольшая поддержка мотивирует развивать бота!"
    )
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🎁 Отправить подарок", url="https://t.me/XAP4KTEP"))
    kb.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=MenuCallback(action="back_to_menu").pack()))
    await message.answer(text, reply_markup=kb.as_markup())

@router.message(Command("support"))
async def cmd_support(message: types.Message):
    text = (
        "🆘 <b>Поддержка</b>\n\n"
        "Если у вас возникли проблемы с оплатой, получением звёзд "
        "или у вас есть предложения – создайте тикет.\n\n"
        "<b>Правила обращения:</b>\n"
        "1. Будьте вежливы\n"
        "2. Опишите проблему подробно\n"
        "3. Приложите скриншоты при необходимости\n"
        "4. Ожидайте ответа в течение 24 часов"
    )
    await message.answer(text, reply_markup=get_support_keyboard())

@router.message(Command("staff"))
async def cmd_staff(message: types.Message):
    from database import get_db_connection
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT username, full_name, role 
        FROM users 
        WHERE role IN ('agent', 'moder', 'admin', 'tech_admin', 'owner')
        ORDER BY 
          CASE role
            WHEN 'owner' THEN 1
            WHEN 'tech_admin' THEN 2
            WHEN 'admin' THEN 3
            WHEN 'moder' THEN 4
            WHEN 'agent' THEN 5
            ELSE 6
          END
    ''')
    staff = cursor.fetchall()
    conn.close()
    if not staff:
        await message.answer("📭 Список администрации пуст.")
        return
    response = "👨‍💼 <b>Администрация бота</b>\n\n"
    for member in staff:
        username, full_name, role = member
        role_display = get_role_display(role)
        if username:
            response += f"{role_display}: @{username}\n"
        else:
            response += f"{role_display}: {full_name}\n"
    await message.answer(response)

@router.message(Command("report"))
async def cmd_report(message: types.Message):
    from main import bot
    user_id = message.from_user.id
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer(
            "❌ Использование: /report (текст проблемы)\n"
            "Например: /report Не пришли звёзды после оплаты"
        )
        return

    text = args[1]
    user = get_user(user_id)
    username = user[2] if user else "без юзернейма"
    full_name = user[3] if user else "Неизвестно"

    ticket_id = create_ticket(
        user_id=user_id,
        subject="Другой вопрос",
        text=text
    )

    try:
        topic_name = f"#{ticket_id} | {full_name} | Другой вопрос"
        topic = await bot.create_forum_topic(
            chat_id=TICKET_GROUP_ID,
            name=topic_name
        )
        topic_id = topic.message_thread_id

        update_ticket_topic(ticket_id, topic_id, topic_name)

        await bot.send_message(
            chat_id=TICKET_GROUP_ID,
            message_thread_id=topic_id,
            text=f"🆕 <b>Тикет (через /report)</b>\n\n"
                 f"👤 Пользователь: {full_name} (@{username})\n"
                 f"🆔 ID: {user_id}\n"
                 f"📝 Тема: Другой вопрос\n\n"
                 f"💬 Сообщение:\n{text}",
            reply_markup=get_ticket_action_keyboard(ticket_id, is_staff=True)
        )
        await message.answer(
            f"✅ Успешно создан тикет #{ticket_id}.\n"
            f"Статус: на проверке."
        )
    except Exception as e:
        logger.error(f"Ошибка создания тикета через /report: {e}")
        await message.answer(f"✅ Тикет #{ticket_id} создан, но не удалось создать тему в группе.")

@router.callback_query(MenuCallback.filter(F.action == "info"))
async def show_info(callback: types.CallbackQuery):
    info_text = (
        "ℹ️ <b>Часто задаваемые вопросы</b>\n\n"
        "🌟 <b>Как происходит выдача товара?</b>\n"
        "Звёзды вы получаете прямо на указанный аккаунт.\n\n"
        "🌟 <b>Могу ли я покупать звёзды для других?</b>\n"
        "Да, нужно указать @username получателя.\n\n"
        "🌟 <b>Есть риск блокировки аккаунта?</b>\n"
        "Нет, мы используем официальные методы.\n\n"
        f"💰 <b>Курс:</b> 1 звезда = {STAR_RATE:.2f}₽\n"
        f"📦 <b>Минимальный заказ:</b> {MIN_STARS} звёзд\n\n"
        "❤️ <b>ПОДДЕРЖАТЬ РАЗРАБОТЧИКА</b>\n"
        "Бот работает для вас 24/7\n"
        "Если хотите сказать спасибо:\n\n"
        "👤 @XAP4KTEP\n\n"
        "Можно отправить:\n"
        "• 🎁 Подарок в Telegram\n"
        "• 💎 USDT (TON)\n"
        "• ⚡ TON"
    )
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🎁 Отправить подарок", url="https://t.me/XAP4KTEP"))
    kb.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=MenuCallback(action="back_to_menu").pack()))
    await callback.message.edit_text(info_text, reply_markup=kb.as_markup())
    await callback.answer()

@router.callback_query(MenuCallback.filter(F.action == "support"))
async def show_support(callback: types.CallbackQuery):
    support_text = (
        "🆘 <b>Поддержка</b>\n\n"
        "Если у вас возникли проблемы с оплатой, получением звёзд "
        "или у вас есть предложения – создайте тикет.\n\n"
        "<b>Правила обращения:</b>\n"
        "1. Будьте вежливы\n"
        "2. Опишите проблему подробно\n"
        "3. Приложите скриншоты при необходимости\n"
        "4. Ожидайте ответа в течение 24 часов"
    )
    await callback.message.edit_text(support_text, reply_markup=get_support_keyboard())
    await callback.answer()

@router.callback_query(F.data == "check_subscription")
async def check_subscription_callback(callback: types.CallbackQuery):
    from main import bot
    user_id = callback.from_user.id
    subscribed = True
    for channel_id in REQUIRED_CHANNELS:
        try:
            member = await bot.get_chat_member(channel_id, user_id)
            if member.status in ['left', 'kicked']:
                subscribed = False
                break
        except Exception as e:
            logger.error(f"Ошибка проверки подписки: {e}")
    if subscribed:
        await callback.message.edit_text(
            "✅ Отлично! Вы подписаны на все каналы.\n\nТеперь вы можете использовать бота:",
            reply_markup=get_main_menu()
        )
    else:
        await callback.answer("❌ Вы не подписаны на все необходимые каналы! Проверьте подписку.", show_alert=True)
    await callback.answer()

@router.callback_query(MenuCallback.filter(F.action == "back_to_menu"))
async def back_to_menu(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "🌟 <b>Главное меню</b> 🌟",
        reply_markup=get_main_menu()
    )
    await callback.answer()

# ========== ОСНОВНОЙ ФУНКЦИОНАЛ МАГАЗИНА ==========

@router.callback_query(MenuCallback.filter(F.action == "buy_manual"))
async def start_manual_buy(callback: types.CallbackQuery, state: FSMContext):
    buy_text = (
        "💰 <b>Покупка звёзд (ручная оплата)</b>\n\n"
        f"Курс: <b>1 звезда = {STAR_RATE:.2f}₽</b>\n"
        f"Минимальная покупка: <b>{MIN_STARS} звёзд</b>\n\n"
        "Введите количество звёзд:"
    )
    await callback.message.edit_text(buy_text, reply_markup=get_back_to_menu_keyboard())
    await state.set_state(PurchaseStates.waiting_for_amount)
    await callback.answer()

@router.message(PurchaseStates.waiting_for_amount)
async def process_stars_amount(message: types.Message, state: FSMContext):
    try:
        amount = int(message.text)
        if amount < MIN_STARS:
            await message.answer(
                f"❌ Сумма должна быть от {MIN_STARS} звёзд!",
                reply_markup=get_back_to_menu_keyboard()
            )
            return
        total_price = amount * STAR_RATE
        await state.update_data(amount=amount, total_price=total_price)
        await message.answer(
            f"✅ Вы хотите купить <b>{amount}</b> звёзд\n"
            f"💳 Сумма к оплате: <b>{total_price:.2f}₽</b>\n\n"
            f"Введите юзернейм получателя (с @):",
            reply_markup=get_back_to_menu_keyboard()
        )
        await state.set_state(PurchaseStates.waiting_for_username)
    except ValueError:
        await message.answer("❌ Пожалуйста, введите число!", reply_markup=get_back_to_menu_keyboard())

@router.message(PurchaseStates.waiting_for_username)
async def process_recipient_username(message: types.Message, state: FSMContext):
    recipient = message.text.strip()
    if not recipient.startswith('@'):
        recipient = '@' + recipient
    await state.update_data(recipient_username=recipient)
    data = await state.get_data()
    promocode_text = (
        f"📋 <b>Детали заказа</b>\n\n"
        f"⭐ Количество звёзд: <b>{data['amount']}</b>\n"
        f"👤 Получатель: <b>{recipient}</b>\n"
        f"💳 Сумма к оплате: <b>{data['total_price']:.2f}₽</b>\n\n"
        f"🎁 Есть промокод?\n"
        f"Введите промокод или нажмите 'Пропустить':"
    )
    await message.answer(promocode_text, reply_markup=get_skip_promocode_keyboard())
    await state.set_state(PurchaseStates.waiting_for_promocode)

@router.message(PurchaseStates.waiting_for_promocode)
async def process_promocode(message: types.Message, state: FSMContext):
    promocode = message.text.strip().upper()
    user_id = message.from_user.id
    if promocode in ("ПРОПУСТИТЬ", "SKIP"):
        await process_final_payment(message, state, 0)
        return
    is_valid, result = check_promocode_valid(promocode, user_id)
    if not is_valid:
        await message.answer(
            f"❌ {result}\n\nПопробуйте другой промокод или нажмите 'Пропустить':",
            reply_markup=get_skip_promocode_keyboard()
        )
        return
    discount_percent = result
    data = await state.get_data()
    original_price = data['total_price']
    discount_amount = original_price * discount_percent / 100
    final_price = original_price - discount_amount
    await state.update_data(
        promocode=promocode,
        discount_percent=discount_percent,
        discount_amount=discount_amount,
        final_price=final_price
    )
    await process_final_payment(message, state, discount_percent)

@router.callback_query(F.data == "skip_promocode", PurchaseStates.waiting_for_promocode)
async def skip_promocode_callback(callback: types.CallbackQuery, state: FSMContext):
    await process_final_payment(callback.message, state, 0)
    await callback.answer()

async def process_final_payment(message: types.Message, state: FSMContext, discount_percent: float = 0):
    data = await state.get_data()
    if discount_percent > 0:
        payment_text = (
            f"📋 <b>Детали заказа</b>\n\n"
            f"⭐ Количество звёзд: <b>{data['amount']}</b>\n"
            f"👤 Получатель: <b>{data['recipient_username']}</b>\n"
            f"🎁 Промокод: <b>{data['promocode']}</b> (-{discount_percent}%)\n"
            f"💳 Исходная сумма: <b>{data['total_price']:.2f}₽</b>\n"
            f"💰 Скидка: <b>{data['discount_amount']:.2f}₽</b>\n"
            f"💳 Итоговая сумма: <b>{data['final_price']:.2f}₽</b>\n\n"
            f"💳 <b>Реквизиты для оплаты:</b>\n"
            f"Сбербанк\n"
            f"<code>2202 2062 8049 9737</code>\n"
            f"Роман М.\n\n"
            f"После оплаты отправьте скриншот перевода:"
        )
    else:
        discount = get_user_active_discount(message.from_user.id)
        if discount:
            data['final_price'] = data['total_price'] * (100 - discount) / 100
            data['discount'] = discount
            payment_text = (
                f"📋 <b>Детали заказа</b>\n\n"
                f"⭐ Количество звёзд: <b>{data['amount']}</b>\n"
                f"👤 Получатель: <b>{data['recipient_username']}</b>\n"
                f"🎁 Скидка по ссылке: {discount}%\n"
                f"💳 Сумма к оплате: <b>{data['final_price']:.2f}₽</b>\n\n"
                f"💳 <b>Реквизиты для оплаты:</b>\n"
                f"Сбербанк\n"
                f"<code>2202 2062 8049 9737</code>\n"
                f"Роман М.\n\n"
                f"После оплаты отправьте скриншот перевода:"
            )
        else:
            payment_text = (
                f"📋 <b>Детали заказа</b>\n\n"
                f"⭐ Количество звёзд: <b>{data['amount']}</b>\n"
                f"👤 Получатель: <b>{data['recipient_username']}</b>\n"
                f"💳 Сумма к оплате: <b>{data['total_price']:.2f}₽</b>\n\n"
                f"💳 <b>Реквизиты для оплаты:</b>\n"
                f"Сбербанк\n"
                f"<code>2202 2062 8049 9737</code>\n"
                f"Роман М.\n\n"
                f"После оплаты отправьте скриншот перевода:"
            )
    await message.answer(payment_text, reply_markup=get_back_to_menu_keyboard())
    await state.set_state(PurchaseStates.waiting_for_screenshot)

@router.message(PurchaseStates.waiting_for_screenshot, F.photo)
async def process_screenshot_photo(message: types.Message, state: FSMContext):
    await _process_screenshot_file(message, state)

@router.message(PurchaseStates.waiting_for_screenshot, F.document)
async def process_screenshot_document(message: types.Message, state: FSMContext):
    if message.document.mime_type
