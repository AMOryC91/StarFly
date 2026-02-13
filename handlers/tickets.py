# FILE: handlers/tickets.py
import logging
from datetime import datetime
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import TICKET_GROUP_ID, TICKET_SUBJECTS, OWNER_ID
from database import (
    get_user, create_ticket, update_ticket_topic, get_ticket, get_ticket_by_topic_id,
    get_ticket_messages, add_ticket_message, get_user_tickets, get_all_tickets,
    update_ticket_status, get_user, get_db_connection, rate_ticket, get_agent_stats,
    log_admin_action
)
from keyboards import (
    TicketCallback, SubjectCallback, get_ticket_subjects_keyboard, get_ticket_action_keyboard,
    get_back_to_menu_keyboard, get_support_keyboard, get_ticket_group_menu_keyboard,
    get_ticket_priority_keyboard, get_ticket_rating_keyboard
)
from states import TicketStates
from utils import has_access, format_datetime, get_user_display_name

logger = logging.getLogger(__name__)

router = Router(name="tickets")

# ========== СОЗДАНИЕ ТИКЕТА ==========
@router.callback_query(F.data == "create_ticket")
async def create_ticket_callback(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "Выберите тему тикета:",
        reply_markup=get_ticket_subjects_keyboard()
    )
    await state.set_state(TicketStates.waiting_for_subject)
    await callback.answer()

@router.callback_query(SubjectCallback.filter(), TicketStates.waiting_for_subject)
async def process_ticket_subject(callback: types.CallbackQuery, callback_data: SubjectCallback, state: FSMContext):
    subject_id = callback_data.subject_id
    subject = TICKET_SUBJECTS[subject_id]
    await state.update_data(ticket_subject=subject)
    await callback.message.edit_text(
        f"Тема: <b>{subject}</b>\n\n"
        f"Теперь введите подробное описание проблемы:",
        reply_markup=get_back_to_menu_keyboard()
    )
    await state.set_state(TicketStates.waiting_for_message)
    await callback.answer()

@router.message(TicketStates.waiting_for_message)
async def process_ticket_message(message: types.Message, state: FSMContext):
    from main import bot
    user_id = message.from_user.id
    data = await state.get_data()
    subject = data.get('ticket_subject')
    if not subject:
        await message.answer("❌ Ошибка: тема тикета не найдена.", reply_markup=get_support_keyboard())
        await state.clear()
        return

    text = message.text
    user = get_user(user_id)
    username = user[2] if user else "без юзернейма"
    full_name = user[3] if user else "Неизвестно"

    ticket_id = create_ticket(user_id, subject, text)

    try:
        topic_name = f"#{ticket_id} | {full_name} | {subject[:30]}"
        topic = await bot.create_forum_topic(chat_id=TICKET_GROUP_ID, name=topic_name)
        topic_id = topic.message_thread_id

        priority = auto_set_priority_text(text)
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE tickets SET priority = ?, topic_id = ?, topic_name = ? WHERE id = ?",
                      (priority, topic_id, topic_name, ticket_id))
        conn.commit()
        conn.close()

        await bot.send_message(
            chat_id=TICKET_GROUP_ID,
            message_thread_id=topic_id,
            text=f"🆕 <b>Тикет #{ticket_id}</b>\n\n"
                 f"👤 Пользователь: {full_name} (@{username})\n"
                 f"🆔 ID: {user_id}\n"
                 f"📝 Тема: {subject}\n"
                 f"🔰 Приоритет: {priority}\n\n"
                 f"💬 Сообщение:\n{text}",
            reply_markup=get_ticket_action_keyboard(ticket_id, is_staff=True)
        )
    except Exception as e:
        logger.error(f"Ошибка создания тикета в группе: {e}")

    await message.answer(
        f"✅ Тикет #{ticket_id} успешно создан!\n"
        f"Тема: {subject}\n\n"
        f"Ваше обращение передано в службу поддержки.",
        reply_markup=get_ticket_action_keyboard(ticket_id)
    )
    await state.clear()

def auto_set_priority_text(text: str) -> str:
    """Авто-расстановка приоритета по ключевым словам."""
    text_lower = text.lower()
    if any(word in text_lower for word in ["бот не работает", "не отвечает", "сломался"]):
        return "⚫"
    if any(word in text_lower for word in ["не пришли", "не получил", "нет звёзд"]):
        return "🔴"
    if any(word in text_lower for word in ["ошибка", "проблема", "баг"]):
        return "🟡"
    return "🟢"

# ========== ОТМЕНА СОЗДАНИЯ ТИКЕТА ==========
@router.callback_query(F.data == "cancel_ticket", TicketStates.waiting_for_subject)
async def cancel_ticket_creation(callback: types.CallbackQuery, state: FSMContext):
    """Отмена создания тикета – сброс состояния и возврат в поддержку."""
    await state.clear()
    await callback.message.edit_text(
        "Создание тикета отменено.",
        reply_markup=get_support_keyboard()
    )
    await callback.answer()

# ========== ПРОСМОТР ТИКЕТОВ ==========
@router.callback_query(F.data == "my_tickets")
async def my_tickets_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    tickets = get_user_tickets(user_id)
    if not tickets:
        await callback.message.edit_text("📭 У вас нет созданных тикетов.", reply_markup=get_support_keyboard())
        await callback.answer()
        return
    response = "📋 <b>Мои тикеты:</b>\n\n"
    for ticket in tickets:
        ticket_id, _, subject, status, topic_id, topic_name, priority, created_at, closed_at, *_ = ticket
        status_icon = "🟢" if status == 'open' else "🔴"
        response += f"{status_icon} {priority} <b>#{ticket_id}</b> - {subject}\n"
        response += f"📅 {format_datetime(created_at)}\n\n"
    await callback.message.edit_text(response, reply_markup=get_support_keyboard())
    await callback.answer()

@router.callback_query(F.data == "back_to_tickets")
async def back_to_tickets(callback: types.CallbackQuery):
    """Возврат к списку тикетов."""
    await my_tickets_callback(callback)

@router.callback_query(TicketCallback.filter(F.action.in_(['reply', 'add_message', 'view'])))
async def show_ticket_details_callback(callback: types.CallbackQuery, callback_data: TicketCallback, state: FSMContext):
    ticket_id = callback_data.ticket_id
    action = callback_data.action
    user_id = callback.from_user.id

    ticket = get_ticket(ticket_id)
    if not ticket:
        await callback.answer("Тикет не найден!", show_alert=True)
        return

    if action in ['reply', 'add_message']:
        if ticket[3] == 'closed':
            await callback.answer("Тикет закрыт! Нельзя добавить сообщение.", show_alert=True)
            return
        await callback.message.edit_text(
            "Введите ваше сообщение для тикета:",
            reply_markup=get_back_to_menu_keyboard()
        )
        await state.set_state(TicketStates.waiting_for_reply)
        await state.update_data(ticket_id=ticket_id)
        await callback.answer()
        return

    await show_ticket_details_internal(callback, ticket_id)

async def show_ticket_details_internal(callback: types.CallbackQuery, ticket_id: int):
    user_id = callback.from_user.id
    ticket = get_ticket(ticket_id)
    if not ticket:
        await callback.answer("Тикет не найден!", show_alert=True)
        return

    ticket_id_db, ticket_user_id, subject, status, topic_id, topic_name, priority, created_at, closed_at, closed_by, rating, rating_comment, agent_id = ticket[:13]
    is_owner = (user_id == ticket_user_id)
    user_role = get_user_role(user_id)
    is_staff = user_role in ['agent', 'moder', 'admin', 'tech_admin', 'owner']

    if not is_owner and not is_staff:
        await callback.answer("У вас нет доступа к этому тикету!", show_alert=True)
        return

    messages = get_ticket_messages(ticket_id)
    status_text = "🟢 Открыт" if status == 'open' else "🔴 Закрыт"
    response = f"📋 <b>Тикет #{ticket_id}</b>\n"
    response += f"📝 Тема: {subject}\n"
    response += f"🔰 Приоритет: {priority}\n"
    response += f"📊 Статус: {status_text}\n"
    response += f"📅 Создан: {format_datetime(created_at)}\n"
    if closed_at:
        response += f"📅 Закрыт: {format_datetime(closed_at)}\n"
    response += f"\n<b>📨 Сообщения:</b>\n\n"

    for msg in messages:
        msg_id, _, user_id_msg, message_text, is_from_support, msg_created_at, username = msg
        time_str = format_datetime(msg_created_at)
        if is_from_support:
            response += f"👨‍💼 <b>Поддержка</b> ({time_str}):\n{message_text}\n\n"
        else:
            user_label = f"@{username}" if username else f"Пользователь"
            response += f"👤 <b>{user_label}</b> ({time_str}):\n{message_text}\n\n"

    await callback.message.edit_text(
        response,
        reply_markup=get_ticket_action_keyboard(ticket_id, is_staff=is_staff)
    )
    await callback.answer()

@router.message(TicketStates.waiting_for_reply)
async def process_ticket_reply(message: types.Message, state: FSMContext):
    from main import bot
    user_id = message.from_user.id
    data = await state.get_data()
    ticket_id = data.get('ticket_id')
    if not ticket_id:
        await message.answer("❌ Ошибка: ID тикета не найден.", reply_markup=get_back_to_menu_keyboard())
        await state.clear()
        return

    ticket = get_ticket(ticket_id)
    if not ticket:
        await message.answer("❌ Тикет не найден!", reply_markup=get_back_to_menu_keyboard())
        await state.clear()
        return

    if ticket[3] == 'closed':
        await message.answer("Тикет закрыт! Нельзя добавить сообщение.", reply_markup=get_back_to_menu_keyboard())
        await state.clear()
        return

    reply_text = message.text
    user_role = get_user_role(user_id)
    is_staff = user_role in ['agent', 'moder', 'admin', 'tech_admin', 'owner']
    add_ticket_message(ticket_id, user_id, reply_text, is_staff)

    if ticket[4]:
        try:
            user = get_user(user_id)
            full_name = user[3] if user else "Неизвестно"
            role_prefix = "👨‍💼 Поддержка" if is_staff else f"👤 {full_name}"
            await bot.send_message(
                chat_id=TICKET_GROUP_ID,
                message_thread_id=ticket[4],
                text=f"{role_prefix}:\n{reply_text}"
            )
        except Exception as e:
            logger.error(f"Ошибка отправки в тему: {e}")

    if is_staff and user_id != ticket[1]:
        try:
            staff_name = message.from_user.full_name
            await bot.send_message(
                ticket[1],
                f"📩 <b>Новый ответ в тикете #{ticket_id}</b>\n\n"
                f"💬 Сообщение от {staff_name}:\n{reply_text}"
            )
        except Exception as e:
            logger.error(f"Ошибка уведомления пользователя: {e}")

    await message.answer("✅ Ваше сообщение добавлено в тикет!", reply_markup=get_back_to_menu_keyboard())
    await state.clear()

# ========== ЗАКРЫТИЕ ТИКЕТА ==========
@router.callback_query(TicketCallback.filter(F.action == "close"))
async def close_ticket_callback(callback: types.CallbackQuery, callback_data: TicketCallback):
    from main import bot
    ticket_id = callback_data.ticket_id
    user_id = callback.from_user.id

    ticket = get_ticket(ticket_id)
    if not ticket:
        await callback.answer("Тикет не найден!", show_alert=True)
        return

    ticket_user_id = ticket[1]
    user_role = get_user_role(user_id)
    if user_id != ticket_user_id and user_role not in ['agent', 'moder', 'admin', 'tech_admin', 'owner']:
        await callback.answer("У вас нет прав для закрытия этого тикета!", show_alert=True)
        return

    update_ticket_status(ticket_id, 'closed')
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE tickets SET closed_by = ? WHERE id = ?", (user_id, ticket_id))
    conn.commit()
    conn.close()

    if ticket[4]:
        try:
            await bot.close_forum_topic(chat_id=TICKET_GROUP_ID, message_thread_id=ticket[4])
        except Exception as e:
            logger.error(f"Ошибка закрытия топика: {e}")

    if user_id != ticket_user_id:
        try:
            closer_name = callback.from_user.full_name
            await bot.send_message(
                ticket_user_id,
                f"🔒 Ваш тикет #{ticket_id} был закрыт {closer_name}.\n\n"
                f"Как оцените работу поддержки?",
                reply_markup=get_ticket_rating_keyboard(ticket_id)
            )
        except Exception as e:
            logger.error(f"Ошибка уведомления о закрытии: {e}")
    else:
        try:
            await bot.send_message(
                ticket_user_id,
                f"✅ Тикет #{ticket_id} закрыт.\n\nКак оцените работу поддержки?",
                reply_markup=get_ticket_rating_keyboard(ticket_id)
            )
        except Exception as e:
            logger.error(f"Ошибка отправки оценки: {e}")

    await callback.message.edit_text(
        f"🔒 Тикет #{ticket_id} закрыт.\nТема: {ticket[2]}",
        reply_markup=get_back_to_menu_keyboard()
    )
    await callback.answer("Тикет закрыт!", show_alert=True)

# ========== ОЦЕНКА ПОДДЕРЖКИ ==========
@router.callback_query(TicketCallback.filter(F.action.startswith("rate_")))
async def rate_ticket_callback(callback: types.CallbackQuery, callback_data: TicketCallback):
    user_id = callback.from_user.id
    ticket_id = callback_data.ticket_id
    rating = int(callback_data.action.split('_')[1])

    ticket = get_ticket(ticket_id)
    if not ticket:
        await callback.answer("❌ Тикет не найден", show_alert=True)
        return
    if ticket[1] != user_id:
        await callback.answer("❌ Вы не можете оценить этот тикет", show_alert=True)
        return

    agent_id = ticket[8] if len(ticket) > 8 else None  # closed_by
    if not agent_id:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT user_id FROM ticket_messages 
            WHERE ticket_id = ? AND is_from_support = 1 
            ORDER BY created_at DESC LIMIT 1
        ''', (ticket_id,))
        row = cursor.fetchone()
        conn.close()
        agent_id = row[0] if row else None

    if agent_id:
        success = rate_ticket(ticket_id, user_id, agent_id, rating)
        if success:
            await callback.message.edit_text(
                f"✅ Спасибо! Ваша оценка ({rating}⭐) сохранена.\nРейтинг агента обновлён."
            )
            logger.info(f"Оценка {rating}⭐ сохранена для тикета {ticket_id}, агент {agent_id}")
        else:
            await callback.message.edit_text("❌ Не удалось сохранить оценку. Попробуйте позже.")
    else:
        await callback.message.edit_text("✅ Спасибо за оценку!")

    await callback.answer()

@router.callback_query(TicketCallback.filter(F.action == "skip_rating"))
async def skip_rating(callback: types.CallbackQuery):
    await callback.message.edit_text("✅ Оценка пропущена. Спасибо за обращение!")
    await callback.answer()

# ========== ИЗМЕНЕНИЕ ПРИОРИТЕТА ==========
@router.callback_query(TicketCallback.filter(F.action == "change_priority"))
async def change_priority_menu(callback: types.CallbackQuery, callback_data: TicketCallback):
    ticket_id = callback_data.ticket_id
    await callback.message.edit_text(
        "⚡ Выберите новый приоритет:",
        reply_markup=get_ticket_priority_keyboard(ticket_id)
    )
    await callback.answer()

@router.callback_query(TicketCallback.filter(F.action.startswith("set_priority_")))
async def set_priority(callback: types.CallbackQuery, callback_data: TicketCallback):
    priority_map = {
        "green": "🟢",
        "yellow": "🟡",
        "red": "🔴",
        "black": "⚫"
    }
    color = callback_data.action.replace("set_priority_", "")
    emoji = priority_map.get(color, "🟢")
    ticket_id = callback_data.ticket_id

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE tickets SET priority = ? WHERE id = ?", (emoji, ticket_id))
    conn.commit()
    ticket = get_ticket(ticket_id)
    if ticket and ticket[4]:
        from main import bot
        try:
            new_name = f"{emoji} #{ticket_id} | {ticket[5]}"
            await bot.edit_forum_topic(
                chat_id=TICKET_GROUP_ID,
                message_thread_id=ticket[4],
                name=new_name
            )
        except Exception as e:
            logger.error(f"Ошибка обновления названия топика: {e}")
    conn.close()

    await callback.answer(f"✅ Приоритет изменён на {emoji}", show_alert=True)
    await show_ticket_details_internal(callback, ticket_id)

# ========== ГРУППОВЫЕ СООБЩЕНИЯ ==========
@router.message(F.chat.id == TICKET_GROUP_ID, F.message_thread_id != None)
async def group_message_handler(message: types.Message):
    """Обрабатывает сообщения из топиков группы. Автоматическое меню НЕ отправляется."""
    await handle_group_message(message)

async def handle_group_message(message: types.Message):
    topic_id = message.message_thread_id
    ticket = get_ticket_by_topic_id(topic_id)
    if not ticket:
        return

    # Проверяем, что тикет открыт
    if ticket[3] == 'closed':
        try:
            await message.reply("❌ Этот тикет закрыт. Новые сообщения не принимаются.")
        except:
            pass
        return

    user_id = message.from_user.id
    user_role = get_user_role(user_id)
    is_staff = user_role in ['agent', 'moder', 'admin', 'tech_admin', 'owner']

    if not is_staff:
        try:
            await message.reply("Пожалуйста, отвечайте через бота (кнопка 'Ответить' в тикете).")
        except:
            pass
        return

    # Сообщение от сотрудника – добавляем в БД, но не отправляем пользователю автоматически
    text = message.text or message.caption or "Вложение"
    add_ticket_message(ticket[0], user_id, text, is_from_support=True)

    try:
        await message.reply("✅ Сообщение сохранено в тикете. Чтобы отправить его пользователю, используйте /answer в боте.")
    except:
        pass

# ========== КОМАНДА ДЛЯ ВЫЗОВА МЕНЮ ТИКЕТОВ В ГРУППЕ ==========
@router.message(Command("ticket_menu"))
async def cmd_ticket_menu(message: types.Message):
    """Отправляет меню поддержки в группу."""
    if message.chat.id != TICKET_GROUP_ID:
        return
    await message.answer(
        "📋 <b>МЕНЮ ПОДДЕРЖКИ</b>",
        reply_markup=get_ticket_group_menu_keyboard()
    )

# ========== КНОПКИ МЕНЮ В ГРУППЕ (ЗАГЛУШКИ) ==========
@router.callback_query(TicketCallback.filter(F.action == "group_open"))
async def group_open_tickets(callback: types.CallbackQuery):
    await callback.answer("Функция в разработке", show_alert=True)

@router.callback_query(TicketCallback.filter(F.action == "group_my"))
async def group_my_tickets(callback: types.CallbackQuery):
    await callback.answer("Функция в разработке", show_alert=True)

@router.callback_query(TicketCallback.filter(F.action == "group_search"))
async def group_search_tickets(callback: types.CallbackQuery):
    await callback.answer("Функция в разработке", show_alert=True)

@router.callback_query(TicketCallback.filter(F.action == "group_rating"))
async def group_rating(callback: types.CallbackQuery):
    await callback.answer("Функция в разработке", show_alert=True)

# ========== СТАТИСТИКА АГЕНТА ==========
@router.callback_query(TicketCallback.filter(F.action == "group_stats"))
async def agent_stats_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if not has_access(user_id, 'agent'):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    stats = get_agent_stats(user_id)
    text = (
        f"📊 <b>СТАТИСТИКА АГЕНТА @{callback.from_user.username or 'no_username'}</b>\n\n"
        f"────────────────────\n"
        f"📋 ТИКЕТЫ:\n"
        f"├─ Всего: {stats['total_tickets']}\n"
        f"├─ Закрыто: {stats['closed_tickets']}\n"
        f"└─ Среднее время ответа: N/A (в разработке)\n\n"
        f"⭐ РЕЙТИНГ:\n"
        f"├─ Средняя оценка: {stats['avg_rating']}/5\n"
        f"├─ Всего оценок: {stats['ratings_count']}\n"
    )
    dist = stats['rating_dist']
    for r in range(5, 0, -1):
        cnt = dist.get(r, 0)
        percent = (cnt / stats['ratings_count'] * 100) if stats['ratings_count'] > 0 else 0
        text += f"├─ {r}⭐: {cnt} ({percent:.0f}%)\n"
    text += "────────────────────"

    await callback.message.edit_text(text, reply_markup=get_back_to_menu_keyboard())
    await callback.answer()

# ========== ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ ==========
def get_user_role(user_id: int) -> str:
    from database import get_user
    user = get_user(user_id)
    if user:
        return user[7] if len(user) > 7 else 'user'
    return 'user'

# ========== КОМАНДЫ ДЛЯ АДМИНИСТРАЦИИ (TICKET MANAGEMENT) ==========
@router.message(Command("ticket"))
async def cmd_ticket(message: types.Message):
    user_id = message.from_user.id
    if not has_access(user_id, 'moder'):
        await message.answer("⛔ Нет доступа")
        return
    args = message.text.split()
    if len(args) < 2:
        await message.answer("❌ Использование: /ticket <id>")
        return
    try:
        ticket_id = int(args[1])
    except:
        await message.answer("❌ Неверный ID")
        return
    ticket = get_ticket(ticket_id)
    if not ticket:
        await message.answer("❌ Тикет не найден")
        return
    user = get_user(ticket[1])
    username = user[2] if user else "Неизвестно"
    text = (
        f"📋 Тикет #{ticket[0]}\n"
        f"👤 Пользователь: @{username} (ID: {ticket[1]})\n"
        f"📅 Создан: {format_datetime(ticket[6])}\n"
        f"📊 Статус: {ticket[3]}\n"
        f"🔰 Приоритет: {ticket[6] if len(ticket)>6 else '🟢'}\n"
        f"📝 Тема: {ticket[2]}\n"
        f"📌 ID темы: {ticket[4]}"
    )
    await message.answer(text)

@router.message(Command("tickets"))
async def cmd_tickets(message: types.Message):
    user_id = message.from_user.id
    if not has_access(user_id, 'moder'):
        await message.answer("⛔ Нет доступа")
        return
    args = message.text.split()
    if len(args) > 1 and args[1].lower() == 'all':
        tickets = get_all_tickets()
        title = "Все тикеты"
    else:
        tickets = get_all_tickets('open')
        title = "Открытые тикеты"
    if not tickets:
        await message.answer(f"📭 {title} отсутствуют.")
        return
    response = f"📋 {title}:\n\n"
    for ticket in tickets[:20]:
        ticket_id, ticket_user_id, subject, status, _, _, priority, created_at = ticket[:8]
        user = get_user(ticket_user_id)
        username = user[2] if user else "Неизвестно"
        response += f"{priority} #{ticket_id} - @{username} - {subject} - {status} - {format_datetime(created_at)}\n\n"
    await message.answer(response)

@router.message(Command("answer"))
async def cmd_answer(message: types.Message):
    user_id = message.from_user.id
    if not has_access(user_id, 'agent'):
        await message.answer("⛔ Нет доступа")
        return
    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        await message.answer("❌ Использование: /answer <id тикета> <текст>")
        return
    try:
        ticket_id = int(args[1])
        answer_text = ' '.join(args[2:])
    except:
        await message.answer("❌ Неверный формат")
        return
    ticket = get_ticket(ticket_id)
    if not ticket:
        await message.answer("❌ Тикет не найден")
        return
    if ticket[3] == 'closed':
        await message.answer("❌ Тикет закрыт. Нельзя отправить ответ.")
        return
    add_ticket_message(ticket_id, user_id, answer_text, is_from_support=True)
    try:
        from main import bot
        await bot.send_message(
            ticket[1],
            f"📩 <b>Ответ на ваш тикет #{ticket_id}</b>\n\n"
            f"<b>Ответ специалиста:</b>\n{answer_text}"
        )
        await message.answer(f"✅ Ответ на тикет #{ticket_id} отправлен!")
    except Exception as e:
        logger.error(f"Ошибка отправки ответа: {e}")
        await message.answer("❌ Не удалось отправить ответ пользователю")

@router.message(Command("creport"))
async def cmd_creport(message: types.Message):
    user_id = message.from_user.id
    if not has_access(user_id, 'agent'):
        await message.answer("⛔ Нет доступа")
        return
    args = message.text.split()
    if len(args) < 2:
        await message.answer("❌ Использование: /creport <id тикета>")
        return
    try:
        ticket_id = int(args[1])
    except:
        await message.answer("❌ Неверный ID")
        return
    ticket = get_ticket(ticket_id)
    if not ticket:
        await message.answer("❌ Тикет не найден")
        return
    if ticket[3] == 'closed':
        await message.answer("❌ Тикет уже закрыт.")
        return
    update_ticket_status(ticket_id, 'closed')
    await message.answer(f"✅ Тикет #{ticket_id} закрыт!")