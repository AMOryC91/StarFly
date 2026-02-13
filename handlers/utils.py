# FILE: handlers/utils.py
import logging
import hashlib
import time
from datetime import datetime
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import (
    BOT_USERNAME, REQUIRED_CHANNELS, STAR_RATE, MIN_STARS,
    ROLE_NAMES, TICKET_GROUP_ID, OWNER_ID
)
from database import (
    get_user, create_user, set_referral_code, add_referral, log_referral_click,
    get_user_by_referral_code, use_discount_link, get_user_referrals,
    create_ticket, update_ticket_topic, get_db_connection
)
from keyboards import (
    MenuCallback, get_main_menu, get_support_keyboard, get_subscription_keyboard,
    get_back_to_menu_keyboard, get_ticket_action_keyboard
)

logger = logging.getLogger(__name__)

router = Router(name="utils")

# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========

def format_datetime(dt_str) -> str:
    if not dt_str:
        return "Неизвестно"
    try:
        date_formats = [
            '%Y-%m-%d %H:%M:%S.%f',
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%d %H:%M',
            '%Y-%m-%d',
            '%d.%m.%Y %H:%M:%S',
            '%d.%m.%Y %H:%M',
            '%d.%m.%Y'
        ]
        for date_format in date_formats:
            try:
                dt = datetime.strptime(dt_str, date_format)
                return dt.strftime('%d.%m.%Y %H:%M')
            except ValueError:
                continue
        return dt_str
    except Exception as e:
        logger.error(f"Ошибка форматирования даты '{dt_str}': {e}")
        return dt_str

def generate_referral_code(user_id: int) -> str:
    code = hashlib.md5(f"ref_{user_id}_{time.time()}".encode()).hexdigest()[:8].upper()
    return code

def get_user_role(user_id: int) -> str:
    from database import get_user
    user = get_user(user_id)
    if user:
        return user[7] if len(user) > 7 else 'user'
    return 'user'

def has_access(user_id: int, required_role: str) -> bool:
    role = get_user_role(user_id)
    role_hierarchy = ['user', 'agent', 'moder', 'admin', 'tech_admin', 'owner']
    try:
        user_index = role_hierarchy.index(role)
        required_index = role_hierarchy.index(required_role)
        return user_index >= required_index
    except ValueError:
        return False

def get_role_display(role: str) -> str:
    return ROLE_NAMES.get(role, '👤 Обычный пользователь')

# ========== КОМАНДА /START ==========
@router.message(Command("start"))
async def cmd_start(message: types.Message):
    """Обработчик команды /start – регистрация, рефералы, скидочные ссылки."""
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

# ========== КОМАНДА /HELP ==========
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

# ========== КОМАНДА /INFO ==========
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
    await message.answer(info_text, reply_markup=kb.as_markup())

# ========== КОМАНДА /DONATE ==========
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

# ========== КОМАНДА /SUPPORT ==========
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

# ========== КОМАНДА /STAFF ==========
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

# ========== КОМАНДА /REPORT ==========
@router.message(Command("report"))
async def cmd_report(message: types.Message):
    """Быстрое создание тикета через команду."""
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

# ========== CALLBACK: ИНФОРМАЦИЯ ==========
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

# ========== CALLBACK: ПОДДЕРЖКА ==========
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

# ========== ПРОВЕРКА ПОДПИСКИ ==========
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

# ========== НАЗАД В ГЛАВНОЕ МЕНЮ ==========
@router.callback_query(MenuCallback.filter(F.action == "back_to_menu"))
async def back_to_menu(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "🌟 <b>Главное меню</b> 🌟",
        reply_markup=get_main_menu()
    )
    await callback.answer()

# ========== ОБРАБОТЧИК ВСЕХ ОСТАЛЬНЫХ СООБЩЕНИЙ ==========
@router.message()
async def handle_other_messages(message: types.Message):
    """Обработчик всех остальных сообщений (не команды, не callback)."""
    if message.text:
        await message.answer(
            "❓ Я не понимаю эту команду.\n"
            "Используйте кнопки меню для навигации.",
            reply_markup=get_main_menu()
        )
    # На другие типы сообщений (стикеры, фото и т.д.) можно не отвечать