# FILE: handlers/admin.py
import logging
import os
import json
import uuid
from datetime import datetime, timedelta
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import (
    OWNER_ID, TECH_ADMIN_ID, ITEMS_PER_PAGE, BACKUP_DIR,
    MINES_GAME_WIN_REWARD, MINES_GAME_LOSE_PENALTY,
    CASINO_BET_AMOUNTS, CASINO_WIN_CHANCE, CASINO_WIN_MULTIPLIER
)
from database import (
    get_user, get_user_role, set_user_role, get_user_by_id_or_username,
    get_all_users, get_user_orders, get_pending_orders, get_order_status, update_order_status,
    get_revenue_for_period, get_active_users_count, get_average_check, get_sales_by_day,
    get_top_buyers_no_admins, get_top_buyers, count_users_by_role,
    update_balance, create_promocode, get_promocode, delete_promocode, get_all_promocodes, update_promocode,
    get_setting, set_setting, clear_settings_cache, get_star_rate, get_min_stars, get_withdraw_commission,
    get_exchange_commission, get_withdraw_min_real, is_rounding_enabled,
    get_referral_levels, get_all_achievements, create_achievement, delete_achievement, update_achievement,
    get_achievement_stats, award_achievement, remove_achievement_from_user,
    create_discount_link, get_all_discount_links, delete_discount_link,
    freeze_user, unfreeze_user, is_user_frozen, get_all_frozen_users,
    create_backup, list_backups, restore_backup, cleanup_old_backups,
    set_maintenance_mode, is_maintenance_mode, get_maintenance_info,
    log_admin_action, get_admin_logs,
    create_sale, get_all_sales, update_sale, delete_sale,
    save_ticket_template, delete_ticket_template, get_all_ticket_templates, get_ticket_template,
    get_birthday_info, set_birthday_info,
    create_mailing, get_pending_mailings, update_mailing_status, get_mailing_stats,
    get_users_by_activity, get_db_connection,
    get_user_by_id_or_username, add_warn, get_warns, remove_warn,
    add_ban, remove_ban, get_ban, is_user_banned, get_all_bans,
    get_ticket, get_all_tickets, add_ticket_message, update_ticket_status
)
from keyboards import (
    AdminCallback, UserCallback, PromocodeCallback, BackupCallback, AchievementCallback,
    get_admin_main_keyboard, get_back_to_admin_keyboard, get_economy_keyboard,
    get_promocodes_main_keyboard, get_promocode_actions_keyboard,
    get_sales_main_keyboard, get_sale_actions_keyboard,
    get_birthday_keyboard, get_templates_main_keyboard, get_template_actions_keyboard,
    get_users_main_keyboard, get_user_actions_keyboard, get_freeze_reason_keyboard,
    get_achievements_main_keyboard, get_achievement_actions_keyboard,
    get_tech_main_keyboard, get_maintenance_keyboard, get_backup_menu_keyboard,
    get_backup_actions_keyboard, get_mailing_main_keyboard, get_mailing_filter_keyboard,
    get_mailing_preview_keyboard, get_logs_filter_keyboard, get_settings_main_keyboard,
    get_pagination_keyboard, get_order_action_keyboard, get_processed_order_keyboard
)
from states import AdminStates
from utils import (
    has_access, format_datetime, format_file_size, format_duration,
    get_role_display, invalidate_settings_cache, invalidate_top_cache
)

logger = logging.getLogger(__name__)

router = Router(name="admin")

# ========== ВХОД В АДМИНКУ ==========
@router.message(Command("admin"))
async def cmd_admin(message: types.Message):
    user = get_user(message.from_user.id)
    username = user[2] or f"id{message.from_user.id}"
    role_display = get_role_display(user[7] if len(user) > 7 else 'user')
    text = f"🔐 <b>АДМИН-ПАНЕЛЬ</b>\n\nВы вошли как: @{username} (Роль: {role_display})"
    await message.answer(text, reply_markup=get_admin_main_keyboard())

@router.callback_query(AdminCallback.filter(F.action == "main"))
async def admin_main_menu(callback: types.CallbackQuery):
    user = get_user(callback.from_user.id)
    username = user[2] or f"id{callback.from_user.id}"
    role_display = get_role_display(user[7] if len(user) > 7 else 'user')
    text = f"🔐 <b>АДМИН-ПАНЕЛЬ</b>\n\nВы вошли как: @{username} (Роль: {role_display})"
    await callback.message.edit_text(text, reply_markup=get_admin_main_keyboard())
    await callback.answer()

@router.callback_query(AdminCallback.filter(F.action == "back"))
async def back_to_admin(callback: types.CallbackQuery):
    await admin_main_menu(callback)

# ========== ЭКОНОМИКА ==========
@router.callback_query(AdminCallback.filter(F.action == "economy_menu"))
async def economy_menu(callback: types.CallbackQuery):
    star_rate = get_star_rate()
    withdraw_comm = get_withdraw_commission() * 100
    exchange_comm = get_exchange_commission() * 100
    min_stars = get_min_stars()
    withdraw_min = get_withdraw_min_real()
    rounding = is_rounding_enabled()
    text = (
        f"💰 <b>УПРАВЛЕНИЕ ЭКОНОМИКОЙ</b>\n\n"
        f"Текущие курсы:\n├─ 1⭐ = {star_rate:.2f}₽\n├─ 1₽ = {1/star_rate:.3f}⭐\n└─ Комиссия вывода: {withdraw_comm:.0f}%\n\n"
        f"Комиссии:\n├─ Вывод: {withdraw_comm:.0f}%\n├─ Обмен реальные→вирт: {exchange_comm:.0f}%\n└─ Обмен вирт→реальные: {exchange_comm:.0f}%\n\n"
        f"Лимиты:\n├─ Мин. покупка: {min_stars}⭐\n├─ Мин. вывод: {withdraw_min}₽\n└─ Округление сумм: [{'✅' if rounding else '❌'}]\n\n"
        f"[💾 СОХРАНИТЬ ВСЕ ИЗМЕНЕНИЯ]"
    )
    await callback.message.edit_text(text, reply_markup=get_economy_keyboard())
    await callback.answer()

# ---- Изменение курса ----
@router.callback_query(AdminCallback.filter(F.action == "edit_star_rate"))
async def edit_star_rate(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("✏️ Введите новый курс (1 звезда = ? рублей):\nНапример: 1.6", reply_markup=get_back_to_admin_keyboard())
    await state.set_state(AdminStates.waiting_star_rate)
    await callback.answer()

@router.message(AdminStates.waiting_star_rate)
async def process_star_rate(message: types.Message, state: FSMContext):
    try:
        rate = float(message.text.replace(',', '.'))
        if rate <= 0:
            raise ValueError
        set_setting('star_rate', str(rate))
        await invalidate_settings_cache()
        await message.answer(f"✅ Курс изменён: 1⭐ = {rate:.2f}₽")
        await state.clear()
        await economy_menu_custom(message)
    except ValueError:
        await message.answer("❌ Введите положительное число.", reply_markup=get_back_to_admin_keyboard())

async def economy_menu_custom(message: types.Message):
    await message.answer("💰 Управление экономикой", reply_markup=get_economy_keyboard())

# ---- Комиссия вывода ----
@router.callback_query(AdminCallback.filter(F.action == "edit_withdraw_commission"))
async def edit_withdraw_commission(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(f"✏️ Введите новую комиссию на вывод (в %):\nТекущая: {get_withdraw_commission()*100:.0f}%", reply_markup=get_back_to_admin_keyboard())
    await state.set_state(AdminStates.waiting_withdraw_commission)
    await callback.answer()

@router.message(AdminStates.waiting_withdraw_commission)
async def process_withdraw_commission(message: types.Message, state: FSMContext):
    try:
        comm = float(message.text.replace(',', '.'))
        if comm < 0 or comm > 100:
            raise ValueError
        set_setting('withdraw_commission', str(comm/100))
        await invalidate_settings_cache()
        await message.answer(f"✅ Комиссия вывода изменена: {comm:.0f}%")
        await state.clear()
        await economy_menu_custom(message)
    except ValueError:
        await message.answer("❌ Введите число от 0 до 100.", reply_markup=get_back_to_admin_keyboard())

# ---- Комиссия обмена реальные→виртуальные ----
@router.callback_query(AdminCallback.filter(F.action == "edit_exchange_commission_real"))
async def edit_exchange_commission_real(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(f"✏️ Введите новую комиссию на обмен реальные→вирт (в %):\nТекущая: {get_exchange_commission()*100:.0f}%", reply_markup=get_back_to_admin_keyboard())
    await state.set_state(AdminStates.waiting_exchange_commission_real)
    await callback.answer()

@router.message(AdminStates.waiting_exchange_commission_real)
async def process_exchange_commission_real(message: types.Message, state: FSMContext):
    try:
        comm = float(message.text.replace(',', '.'))
        if comm < 0 or comm > 100:
            raise ValueError
        set_setting('exchange_commission', str(comm/100))
        await invalidate_settings_cache()
        await message.answer(f"✅ Комиссия обмена реальные→вирт изменена: {comm:.0f}%")
        await state.clear()
        await economy_menu_custom(message)
    except ValueError:
        await message.answer("❌ Введите число от 0 до 100.", reply_markup=get_back_to_admin_keyboard())

# ---- Комиссия обмена виртуальные→реальные ----
@router.callback_query(AdminCallback.filter(F.action == "edit_exchange_commission_virtual"))
async def edit_exchange_commission_virtual(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(f"✏️ Введите новую комиссию на обмен вирт→реальные (в %):\nТекущая: {get_setting('virtual_to_real_commission', '50')}%", reply_markup=get_back_to_admin_keyboard())
    await state.set_state(AdminStates.waiting_exchange_commission_virtual)
    await callback.answer()

@router.message(AdminStates.waiting_exchange_commission_virtual)
async def process_exchange_commission_virtual(message: types.Message, state: FSMContext):
    try:
        comm = float(message.text.replace(',', '.'))
        if comm < 0 or comm > 100:
            raise ValueError
        set_setting('virtual_to_real_commission', str(comm))
        await invalidate_settings_cache()
        await message.answer(f"✅ Комиссия обмена вирт→реальные изменена: {comm:.0f}%")
        await state.clear()
        await economy_menu_custom(message)
    except ValueError:
        await message.answer("❌ Введите число от 0 до 100.", reply_markup=get_back_to_admin_keyboard())

# ---- Мин. покупка ----
@router.callback_query(AdminCallback.filter(F.action == "edit_min_stars"))
async def edit_min_stars(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(f"✏️ Введите минимальное количество звёзд для покупки:\nТекущее: {get_min_stars()}", reply_markup=get_back_to_admin_keyboard())
    await state.set_state(AdminStates.waiting_min_stars)
    await callback.answer()

@router.message(AdminStates.waiting_min_stars)
async def process_min_stars(message: types.Message, state: FSMContext):
    try:
        min_stars = int(message.text)
        if min_stars < 1:
            raise ValueError
        set_setting('min_stars', str(min_stars))
        await invalidate_settings_cache()
        await message.answer(f"✅ Минимальная покупка изменена: {min_stars}⭐")
        await state.clear()
        await economy_menu_custom(message)
    except ValueError:
        await message.answer("❌ Введите целое положительное число.", reply_markup=get_back_to_admin_keyboard())

# ---- Мин. вывод ----
@router.callback_query(AdminCallback.filter(F.action == "edit_withdraw_min"))
async def edit_withdraw_min(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(f"✏️ Введите минимальную сумму вывода в реальных звёздах:\nТекущая: {get_withdraw_min_real()}₽", reply_markup=get_back_to_admin_keyboard())
    await state.set_state(AdminStates.waiting_min_withdraw)
    await callback.answer()

@router.message(AdminStates.waiting_min_withdraw)
async def process_withdraw_min(message: types.Message, state: FSMContext):
    try:
        min_withdraw = int(message.text)
        if min_withdraw < 1:
            raise ValueError
        set_setting('withdraw_min_real', str(min_withdraw))
        await invalidate_settings_cache()
        await message.answer(f"✅ Минимальный вывод изменён: {min_withdraw}₽")
        await state.clear()
        await economy_menu_custom(message)
    except ValueError:
        await message.answer("❌ Введите целое положительное число.", reply_markup=get_back_to_admin_keyboard())

# ---- Округление ----
@router.callback_query(AdminCallback.filter(F.action == "toggle_rounding"))
async def toggle_rounding(callback: types.CallbackQuery):
    current = is_rounding_enabled()
    set_setting('rounding_enabled', '0' if current else '1')
    await invalidate_settings_cache()
    await callback.answer(f"✅ Округление {'включено' if not current else 'выключено'}", show_alert=True)
    await economy_menu(callback)

@router.callback_query(AdminCallback.filter(F.action == "save_economy"))
async def save_economy(callback: types.CallbackQuery):
    await callback.answer("✅ Все изменения сохранены", show_alert=True)
    await economy_menu(callback)

# ========== ПРОМОКОДЫ ==========
@router.callback_query(AdminCallback.filter(F.action == "promocodes_menu"))
async def promocodes_menu(callback: types.CallbackQuery):
    await callback.message.edit_text("🎁 <b>УПРАВЛЕНИЕ ПРОМОКОДАМИ</b>", reply_markup=get_promocodes_main_keyboard())
    await callback.answer()

@router.callback_query(AdminCallback.filter(F.action == "create_promocode"))
async def create_promocode_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Введите код промокода (например: SUMMER50):", reply_markup=get_back_to_admin_keyboard())
    await state.set_state(AdminStates.waiting_promo_code)
    await callback.answer()

@router.message(AdminStates.waiting_promo_code)
async def process_promo_code(message: types.Message, state: FSMContext):
    code = message.text.strip().upper()
    await state.update_data(promo_code=code)
    await message.answer("Введите размер скидки в % (только число):")
    await state.set_state(AdminStates.waiting_promo_discount)

@router.message(AdminStates.waiting_promo_discount)
async def process_promo_discount(message: types.Message, state: FSMContext):
    try:
        discount = int(message.text)
        if discount < 0 or discount > 100:
            raise ValueError
        await state.update_data(discount=discount)
        await message.answer("Введите максимальное количество активаций (0 = без лимита):")
        await state.set_state(AdminStates.waiting_promo_max_uses)
    except ValueError:
        await message.answer("❌ Введите целое число от 0 до 100.")

@router.message(AdminStates.waiting_promo_max_uses)
async def process_promo_max_uses(message: types.Message, state: FSMContext):
    try:
        max_uses = int(message.text)
        if max_uses < 0:
            raise ValueError
        await state.update_data(max_uses=max_uses)
        await message.answer("Введите срок действия в днях (0 = бессрочно):")
        await state.set_state(AdminStates.waiting_promo_expires)
    except ValueError:
        await message.answer("❌ Введите целое неотрицательное число.")

@router.message(AdminStates.waiting_promo_expires)
async def process_promo_expires(message: types.Message, state: FSMContext):
    try:
        days = int(message.text)
        data = await state.get_data()
        code = data['promo_code']
        discount = data['discount']
        max_uses = data['max_uses']
        expires_at = None
        if days > 0:
            expires_at = datetime.now() + timedelta(days=days)
        create_promocode(code, discount, max_uses, expires_at)
        await message.answer(f"✅ Промокод {code} создан!")
        await state.clear()
        await promocodes_menu_custom(message)
    except ValueError:
        await message.answer("❌ Введите целое число.")

async def promocodes_menu_custom(message: types.Message):
    await message.answer("🎁 Управление промокодами", reply_markup=get_promocodes_main_keyboard())

@router.callback_query(AdminCallback.filter(F.action == "list_promocodes"))
async def list_promocodes(callback: types.CallbackQuery, callback_data: AdminCallback):
    page = callback_data.page
    promocodes = get_all_promocodes()
    if not promocodes:
        await callback.message.edit_text("📭 Промокоды не найдены.", reply_markup=get_back_to_admin_keyboard())
        await callback.answer()
        return
    total_pages = (len(promocodes) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    page = max(1, min(page, total_pages))
    start = (page - 1) * ITEMS_PER_PAGE
    end = start + ITEMS_PER_PAGE
    current = promocodes[start:end]

    text = f"🎁 <b>СПИСОК ПРОМОКОДОВ</b> (страница {page}/{total_pages})\n\n"
    for promo in current:
        promo_id, code, discount, max_uses, used, created, expires = promo
        text += f"🔹 <b>{code}</b>\n├─ Скидка: {discount}%\n├─ Активаций: {used}/{max_uses if max_uses>0 else '∞'}\n"
        text += f"└─ Действ. до: {format_datetime(expires) if expires else 'бессрочно'}\n"
        text += f"   [✏️] [🗑️]\n\n"

    keyboard = get_pagination_keyboard(page, total_pages, "list_promocodes")
    builder = InlineKeyboardBuilder()
    builder.attach(InlineKeyboardBuilder.from_markup(keyboard))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=AdminCallback(action="promocodes_menu").pack()))
    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()

@router.callback_query(PromocodeCallback.filter(F.action == "edit"))
async def edit_promocode(callback: types.CallbackQuery, callback_data: PromocodeCallback, state: FSMContext):
    promo_id = callback_data.promo_id
    await state.update_data(promo_id=promo_id, edit_page=callback_data.page)
    await callback.message.edit_text("Введите новый процент скидки:", reply_markup=get_back_to_admin_keyboard())
    await state.set_state(AdminStates.waiting_promo_discount)

@router.callback_query(PromocodeCallback.filter(F.action == "delete"))
async def delete_promocode_handler(callback: types.CallbackQuery, callback_data: PromocodeCallback):
    delete_promocode(callback_data.promo_id)
    await callback.answer("✅ Промокод удалён", show_alert=True)
    await list_promocodes(callback, AdminCallback(action="list_promocodes", page=callback_data.page))

@router.callback_query(AdminCallback.filter(F.action == "promo_stats"))
async def promo_stats(callback: types.CallbackQuery):
    promocodes = get_all_promocodes()
    total = len(promocodes)
    total_used = sum(p[4] for p in promocodes)
    text = f"📊 <b>Статистика промокодов</b>\n\nВсего создано: {total}\nВсего использований: {total_used}"
    await callback.message.edit_text(text, reply_markup=get_back_to_admin_keyboard())
    await callback.answer()

# ========== АКЦИИ ==========
@router.callback_query(AdminCallback.filter(F.action == "sales_menu"))
async def sales_menu(callback: types.CallbackQuery):
    await callback.message.edit_text("📅 <b>УПРАВЛЕНИЕ АКЦИЯМИ</b>", reply_markup=get_sales_main_keyboard())
    await callback.answer()

@router.callback_query(AdminCallback.filter(F.action == "create_sale"))
async def create_sale_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Введите название акции:", reply_markup=get_back_to_admin_keyboard())
    await state.set_state(AdminStates.waiting_sale_name)
    await callback.answer()

@router.message(AdminStates.waiting_sale_name)
async def process_sale_name(message: types.Message, state: FSMContext):
    await state.update_data(sale_name=message.text)
    await message.answer("Выберите тип акции:\n1 - Скидка %\n2 - Кэшбэк %\n3 - Подарок (звёзды)")
    await state.set_state(AdminStates.waiting_sale_type)

@router.message(AdminStates.waiting_sale_type)
async def process_sale_type(message: types.Message, state: FSMContext):
    try:
        t = int(message.text)
        if t not in [1, 2, 3]:
            raise ValueError
        type_map = {1: 'discount', 2: 'cashback', 3: 'gift'}
        await state.update_data(sale_type=type_map[t])
        await message.answer("Введите значение (для скидки/кэшбэка - проценты, для подарка - количество звёзд):")
        await state.set_state(AdminStates.waiting_sale_value)
    except ValueError:
        await message.answer("❌ Введите 1, 2 или 3.")

@router.message(AdminStates.waiting_sale_value)
async def process_sale_value(message: types.Message, state: FSMContext):
    try:
        value = int(message.text)
        await state.update_data(sale_value=value)
        await message.answer("Введите дату и время начала (в формате ДД.ММ.ГГГГ ЧЧ:ММ):")
        await state.set_state(AdminStates.waiting_sale_start)
    except ValueError:
        await message.answer("❌ Введите целое число.")

@router.message(AdminStates.waiting_sale_start)
async def process_sale_start(message: types.Message, state: FSMContext):
    try:
        start = datetime.strptime(message.text, '%d.%m.%Y %H:%M')
        await state.update_data(sale_start=start)
        await message.answer("Введите дату и время окончания (в формате ДД.ММ.ГГГГ ЧЧ:ММ):")
        await state.set_state(AdminStates.waiting_sale_end)
    except ValueError:
        await message.answer("❌ Неверный формат. Используйте ДД.ММ.ГГГГ ЧЧ:ММ")

@router.message(AdminStates.waiting_sale_end)
async def process_sale_end(message: types.Message, state: FSMContext):
    try:
        end = datetime.strptime(message.text, '%d.%m.%Y %H:%M')
        data = await state.get_data()
        sale_id = create_sale(
            name=data['sale_name'],
            discount_type=data['sale_type'],
            discount_value=data['sale_value'],
            start_date=data['sale_start'],
            end_date=end
        )
        await message.answer(f"✅ Акция '{data['sale_name']}' создана! ID: {sale_id}")
        await state.clear()
        await sales_menu_custom(message)
    except ValueError:
        await message.answer("❌ Неверный формат.")

async def sales_menu_custom(message: types.Message):
    await message.answer("📅 Управление акциями", reply_markup=get_sales_main_keyboard())

@router.callback_query(AdminCallback.filter(F.action == "list_sales"))
async def list_sales(callback: types.CallbackQuery, callback_data: AdminCallback):
    page = callback_data.page
    sales = get_all_sales()
    if not sales:
        await callback.message.edit_text("📭 Акции не найдены.", reply_markup=get_back_to_admin_keyboard())
        await callback.answer()
        return
    total_pages = (len(sales) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    page = max(1, min(page, total_pages))
    start = (page - 1) * ITEMS_PER_PAGE
    end = start + ITEMS_PER_PAGE
    current = sales[start:end]

    text = f"📅 <b>СПИСОК АКЦИЙ</b> (стр. {page}/{total_pages})\n\n"
    for sale in current:
        status_icon = "🟢" if sale.get('active', True) else "🔴"
        type_display = {
            'discount': f"Скидка {sale['value']}%",
            'cashback': f"Кэшбэк {sale['value']}%",
            'gift': f"Подарок {sale['value']}⭐"
        }.get(sale['type'], sale['type'])
        text += f"{status_icon} <b>{sale['name']}</b>\n├─ Тип: {type_display}\n├─ Старт: {format_datetime(sale['start'])}\n"
        text += f"├─ Окончание: {format_datetime(sale['end'])}\n└─ [✏️] [🗑️] [⏸️ ПАУЗА]\n\n"

    keyboard = get_pagination_keyboard(page, total_pages, "list_sales")
    builder = InlineKeyboardBuilder()
    builder.attach(InlineKeyboardBuilder.from_markup(keyboard))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=AdminCallback(action="sales_menu").pack()))
    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()

@router.callback_query(AdminCallback.filter(F.action == "edit_sale"))
async def edit_sale(callback: types.CallbackQuery, callback_data: AdminCallback, state: FSMContext):
    sale_id = callback_data.target_id
    page = callback_data.page
    await state.update_data(sale_id=sale_id, sale_page=page)
    await callback.message.edit_text(
        "Что редактируем?\n1 - Название\n2 - Тип/значение\n3 - Даты\n4 - Отмена",
        reply_markup=get_back_to_admin_keyboard()
    )
    await state.set_state(AdminStates.waiting_generic_number)
    await callback.answer()

@router.callback_query(AdminCallback.filter(F.action == "delete_sale"))
async def delete_sale_handler(callback: types.CallbackQuery, callback_data: AdminCallback):
    if delete_sale(callback_data.target_id):
        await callback.answer("✅ Акция удалена", show_alert=True)
    else:
        await callback.answer("❌ Ошибка удаления", show_alert=True)
    await list_sales(callback, AdminCallback(action="list_sales", page=callback_data.page))

@router.callback_query(AdminCallback.filter(F.action == "toggle_sale"))
async def toggle_sale(callback: types.CallbackQuery, callback_data: AdminCallback):
    sale_id = callback_data.target_id
    sales = get_all_sales()
    for sale in sales:
        if sale['id'] == sale_id:
            new_status = not sale.get('active', True)
            update_sale(sale_id, {'active': new_status})
            await callback.answer(f"Акция {'возобновлена' if new_status else 'приостановлена'}", show_alert=True)
            break
    await list_sales(callback, AdminCallback(action="list_sales", page=callback_data.page))

@router.callback_query(AdminCallback.filter(F.action == "toggle_auto_sale"))
async def toggle_auto_sale(callback: types.CallbackQuery):
    current = get_setting('auto_sale', '0')
    set_setting('auto_sale', '0' if current == '1' else '1')
    await callback.answer(f"🤖 Авто-применение акций {'включено' if current=='0' else 'выключено'}", show_alert=True)
    await sales_menu(callback)

# ========== ДЕНЬ РОЖДЕНИЯ БОТА ==========
@router.callback_query(AdminCallback.filter(F.action == "birthday_menu"))
async def birthday_menu(callback: types.CallbackQuery):
    info = get_birthday_info()
    date = info['date'] if info['date'] else "не установлена"
    status = "⏸️ ОТКЛЮЧЕНО" if not info['enabled'] else "✅ ВКЛЮЧЕНО"
    text = (
        f"🎂 <b>ДЕНЬ РОЖДЕНИЯ БОТА</b>\n\n"
        f"Дата события: {date}\nСтатус: [{status}]\n\n"
        f"────────────────────\nКОНТЕНТ:\n\n📝 ТЕКСТ\n━━━━━━━━━━━━━━━━\n{info['text'][:100]}{'...' if info['text'] and len(info['text'])>100 else ''}\n━━━━━━━━━━━━━━━━\n[✏️] [🗑️]\n\n"
        f"🖼️ ФОТО/ГИФКА\n━━━━━━━━━━━━━━━━\n{info['photo'] if info['photo'] else 'не задано'}\n━━━━━━━━━━━━━━━━\n[➕] [🗑️]\n\n"
        f"🎵 АУДИО/ВОЙС\n━━━━━━━━━━━━━━━━\n{info['audio'] if info['audio'] else 'не задано'}\n━━━━━━━━━━━━━━━━\n[➕] [🗑️]\n\n"
        f"🎨 СТИКЕР\n━━━━━━━━━━━━━━━━\n{info['sticker'] if info['sticker'] else 'не задан'}\n━━━━━━━━━━━━━━━━\n[➕] [🗑️]\n\n"
        f"────────────────────\nРежим отправки: {'Рандомный' if info['mode']=='random' else 'Все подряд' if info['mode']=='all' else 'Только текст'}\n\n[💾 СОХРАНИТЬ]"
    )
    await callback.message.edit_text(text, reply_markup=get_birthday_keyboard())
    await callback.answer()

@router.callback_query(AdminCallback.filter(F.action == "edit_birthday_text"))
async def edit_birthday_text(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("✏️ Введите новый текст поздравления:", reply_markup=get_back_to_admin_keyboard())
    await state.set_state(AdminStates.waiting_birthday_text)
    await callback.answer()

@router.message(AdminStates.waiting_birthday_text)
async def process_birthday_text(message: types.Message, state: FSMContext):
    set_setting('birthday_text', message.text)
    await message.answer("✅ Текст сохранён!")
    await state.clear()
    await birthday_menu_custom(message)

@router.callback_query(AdminCallback.filter(F.action == "delete_birthday_text"))
async def delete_birthday_text(callback: types.CallbackQuery):
    set_setting('birthday_text', '')
    await callback.answer("🗑️ Текст удалён", show_alert=True)
    await birthday_menu(callback)

@router.callback_query(AdminCallback.filter(F.action == "edit_birthday_photo"))
async def edit_birthday_photo(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("🖼️ Отправьте фото для дня рождения:", reply_markup=get_back_to_admin_keyboard())
    await state.set_state(AdminStates.waiting_birthday_photo)
    await callback.answer()

@router.message(AdminStates.waiting_birthday_photo, F.photo)
async def process_birthday_photo(message: types.Message, state: FSMContext):
    file_id = message.photo[-1].file_id
    set_setting('birthday_photo', file_id)
    await message.answer("✅ Фото сохранено!")
    await state.clear()
    await birthday_menu_custom(message)

@router.message(AdminStates.waiting_birthday_photo, F.document)
async def process_birthday_photo_doc(message: types.Message, state: FSMContext):
    if message.document.mime_type.startswith('image/'):
        file_id = message.document.file_id
        set_setting('birthday_photo', file_id)
        await message.answer("✅ Фото сохранено!")
        await state.clear()
        await birthday_menu_custom(message)
    else:
        await message.answer("❌ Отправьте изображение.")

@router.callback_query(AdminCallback.filter(F.action == "delete_birthday_photo"))
async def delete_birthday_photo(callback: types.CallbackQuery):
    set_setting('birthday_photo', '')
    await callback.answer("🗑️ Фото удалено", show_alert=True)
    await birthday_menu(callback)

@router.callback_query(AdminCallback.filter(F.action == "edit_birthday_audio"))
async def edit_birthday_audio(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("🎵 Отправьте аудиофайл или голосовое сообщение:", reply_markup=get_back_to_admin_keyboard())
    await state.set_state(AdminStates.waiting_birthday_audio)
    await callback.answer()

@router.message(AdminStates.waiting_birthday_audio, F.audio)
async def process_birthday_audio(message: types.Message, state: FSMContext):
    file_id = message.audio.file_id
    set_setting('birthday_audio', file_id)
    await message.answer("✅ Аудио сохранено!")
    await state.clear()
    await birthday_menu_custom(message)

@router.message(AdminStates.waiting_birthday_audio, F.voice)
async def process_birthday_voice(message: types.Message, state: FSMContext):
    file_id = message.voice.file_id
    set_setting('birthday_audio', file_id)
    await message.answer("✅ Голосовое сообщение сохранено!")
    await state.clear()
    await birthday_menu_custom(message)

@router.callback_query(AdminCallback.filter(F.action == "delete_birthday_audio"))
async def delete_birthday_audio(callback: types.CallbackQuery):
    set_setting('birthday_audio', '')
    await callback.answer("🗑️ Аудио удалено", show_alert=True)
    await birthday_menu(callback)

@router.callback_query(AdminCallback.filter(F.action == "edit_birthday_sticker"))
async def edit_birthday_sticker(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("🎨 Отправьте стикер:", reply_markup=get_back_to_admin_keyboard())
    await state.set_state(AdminStates.waiting_birthday_sticker)
    await callback.answer()

@router.message(AdminStates.waiting_birthday_sticker, F.sticker)
async def process_birthday_sticker(message: types.Message, state: FSMContext):
    file_id = message.sticker.file_id
    set_setting('birthday_sticker', file_id)
    await message.answer("✅ Стикер сохранён!")
    await state.clear()
    await birthday_menu_custom(message)

@router.callback_query(AdminCallback.filter(F.action == "delete_birthday_sticker"))
async def delete_birthday_sticker(callback: types.CallbackQuery):
    set_setting('birthday_sticker', '')
    await callback.answer("🗑️ Стикер удалён", show_alert=True)
    await birthday_menu(callback)

@router.callback_query(AdminCallback.filter(F.action == "edit_birthday_date"))
async def edit_birthday_date(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Введите дату дня рождения бота в формате ДД.ММ.ГГГГ:", reply_markup=get_back_to_admin_keyboard())
    await state.set_state(AdminStates.waiting_birthday_date)
    await callback.answer()

@router.message(AdminStates.waiting_birthday_date)
async def process_birthday_date(message: types.Message, state: FSMContext):
    try:
        datetime.strptime(message.text, '%d.%m.%Y')
        set_setting('birthday_date', message.text)
        await message.answer("✅ Дата сохранена!")
        await state.clear()
        await birthday_menu_custom(message)
    except ValueError:
        await message.answer("❌ Неверный формат. Используйте ДД.ММ.ГГГГ")

@router.callback_query(AdminCallback.filter(F.action == "birthday_mode"))
async def birthday_mode(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "Выберите режим отправки:\n1 - Рандомный\n2 - Все подряд\n3 - Только текст",
        reply_markup=get_back_to_admin_keyboard()
    )
    await state.set_state(AdminStates.waiting_birthday_mode)
    await callback.answer()

@router.message(AdminStates.waiting_birthday_mode)
async def process_birthday_mode(message: types.Message, state: FSMContext):
    mode_map = {'1': 'random', '2': 'all', '3': 'text'}
    if message.text in mode_map:
        set_setting('birthday_mode', mode_map[message.text])
        await message.answer("✅ Режим отправки сохранён!")
    else:
        await message.answer("❌ Введите 1, 2 или 3.")
    await state.clear()
    await birthday_menu_custom(message)

@router.callback_query(AdminCallback.filter(F.action == "toggle_birthday"))
async def toggle_birthday(callback: types.CallbackQuery):
    current = get_setting('birthday_enabled', '0')
    set_setting('birthday_enabled', '0' if current == '1' else '1')
    await callback.answer(f"🎂 День рождения {'включён' if current=='0' else 'выключен'}", show_alert=True)
    await birthday_menu(callback)

@router.callback_query(AdminCallback.filter(F.action == "save_birthday"))
async def save_birthday(callback: types.CallbackQuery):
    await callback.answer("💾 Настройки дня рождения сохранены", show_alert=True)
    await birthday_menu(callback)

async def birthday_menu_custom(message: types.Message):
    await message.answer("🎂 Настройки дня рождения", reply_markup=get_birthday_keyboard())

# ========== ШАБЛОНЫ ТИКЕТОВ ==========
@router.callback_query(AdminCallback.filter(F.action == "templates_menu"))
async def templates_menu(callback: types.CallbackQuery):
    await callback.message.edit_text("📋 <b>ШАБЛОНЫ ОТВЕТОВ</b>", reply_markup=get_templates_main_keyboard())
    await callback.answer()

@router.callback_query(AdminCallback.filter(F.action == "create_template"))
async def create_template_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Введите название шаблона (например: ПРИВЕТСТВИЕ):", reply_markup=get_back_to_admin_keyboard())
    await state.set_state(AdminStates.waiting_template_name)
    await callback.answer()

@router.message(AdminStates.waiting_template_name)
async def process_template_name(message: types.Message, state: FSMContext):
    await state.update_data(template_name=message.text.strip().upper())
    await message.answer("Введите текст шаблона. Используйте переменные: {username}, {user_id}, {ticket_id}, {order_id}, {amount}")
    await state.set_state(AdminStates.waiting_template_text)

@router.message(AdminStates.waiting_template_text)
async def process_template_text(message: types.Message, state: FSMContext):
    data = await state.get_data()
    name = data['template_name']
    save_ticket_template(name, message.text)
    await message.answer(f"✅ Шаблон '{name}' сохранён!")
    await state.clear()
    await templates_menu_custom(message)

async def templates_menu_custom(message: types.Message):
    await message.answer("📋 Шаблоны тикетов", reply_markup=get_templates_main_keyboard())

@router.callback_query(AdminCallback.filter(F.action == "list_templates"))
async def list_templates(callback: types.CallbackQuery, callback_data: AdminCallback):
    page = callback_data.page
    templates = get_all_ticket_templates()
    if not templates:
        await callback.message.edit_text("📭 Шаблоны не найдены.", reply_markup=get_back_to_admin_keyboard())
        await callback.answer()
        return
    items = list(templates.items())
    total_pages = (len(items) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    page = max(1, min(page, total_pages))
    start = (page - 1) * ITEMS_PER_PAGE
    end = start + ITEMS_PER_PAGE
    current = items[start:end]

    text = f"📋 <b>СПИСОК ШАБЛОНОВ</b> (стр. {page}/{total_pages})\n\n"
    for name, content in current:
        text += f"📌 <b>{name}</b>\n━━━━━━━━━━━━━━━━\n{content[:100]}{'...' if len(content)>100 else ''}\n━━━━━━━━━━━━━━━━\n[✏️] [🗑️] [📋 КОПИРОВАТЬ]\n\n"

    keyboard = get_pagination_keyboard(page, total_pages, "list_templates")
    builder = InlineKeyboardBuilder()
    builder.attach(InlineKeyboardBuilder.from_markup(keyboard))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=AdminCallback(action="templates_menu").pack()))
    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()

@router.callback_query(AdminCallback.filter(F.action == "edit_template"))
async def edit_template(callback: types.CallbackQuery, callback_data: AdminCallback, state: FSMContext):
    template_name = callback_data.data
    await state.update_data(template_name=template_name, edit_page=callback_data.page)
    await callback.message.edit_text(f"✏️ Редактирование шаблона '{template_name}'\n\nВведите новый текст:", reply_markup=get_back_to_admin_keyboard())
    await state.set_state(AdminStates.waiting_template_text)

@router.callback_query(AdminCallback.filter(F.action == "delete_template"))
async def delete_template(callback: types.CallbackQuery, callback_data: AdminCallback):
    template_name = callback_data.data
    delete_ticket_template(template_name)
    await callback.answer(f"🗑️ Шаблон '{template_name}' удалён", show_alert=True)
    await list_templates(callback, AdminCallback(action="list_templates", page=callback_data.page))

@router.callback_query(AdminCallback.filter(F.action == "copy_template"))
async def copy_template(callback: types.CallbackQuery, callback_data: AdminCallback, state: FSMContext):
    template_name = callback_data.data
    content = get_ticket_template(template_name)
    await state.update_data(template_content=content)
    await callback.message.edit_text(f"📋 Копирование шаблона '{template_name}'\n\nВведите новое название для копии:", reply_markup=get_back_to_admin_keyboard())
    await state.set_state(AdminStates.waiting_template_name)

# ========== УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ ==========
@router.callback_query(AdminCallback.filter(F.action == "users_menu"))
async def users_menu(callback: types.CallbackQuery):
    await callback.message.edit_text("👥 <b>УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ</b>", reply_markup=get_users_main_keyboard())
    await callback.answer()

@router.callback_query(AdminCallback.filter(F.action == "user_search"))
async def user_search_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("🔍 Введите @username или ID пользователя:", reply_markup=get_back_to_admin_keyboard())
    await state.set_state(AdminStates.waiting_user_search)
    await callback.answer()

@router.message(AdminStates.waiting_user_search)
async def process_user_search(message: types.Message, state: FSMContext):
    identifier = message.text.strip()
    user = get_user_by_id_or_username(identifier)
    if not user:
        await message.answer("❌ Пользователь не найден.", reply_markup=get_back_to_admin_keyboard())
        return
    await state.clear()
    await show_user_profile(message, user)

async def show_user_profile(message: types.Message, user: tuple):
    user_id = user[1]
    username = user[2] or "без юзернейма"
    full_name = user[3]
    virtual_balance = user[5]
    total_spent = user[6]
    role = user[7] if len(user) > 7 else 'user'
    role_display = get_role_display(role)
    frozen = is_user_frozen(user_id)
    freeze_info = get_freeze_info(user_id) if frozen else None

    text = f"👤 <b>ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ</b>\n\n🆔 ID: <code>{user_id}</code>\n👤 Имя: {full_name}\n📱 Юзернейм: @{username}\n🎖️ Роль: {role_display}\n🎮 Вирт. баланс: {virtual_balance} ⭐\n📊 Потрачено: {total_spent:.2f}₽\n"
    if frozen:
        text += f"\n❄️ ЗАМОРОЖЕН: {freeze_info[0] if freeze_info else 'Не указано'}\n"
    await message.answer(text, reply_markup=get_user_actions_keyboard(user_id))

@router.callback_query(UserCallback.filter(F.action == "freeze"))
async def freeze_user_start(callback: types.CallbackQuery, callback_data: UserCallback, state: FSMContext):
    user_id = callback_data.user_id
    await state.update_data(target_user_id=user_id)
    await callback.message.edit_text("❄️ <b>ЗАМОРОЗКА ПОЛЬЗОВАТЕЛЯ</b>\n\nВыберите причину или введите свою:", reply_markup=get_freeze_reason_keyboard(user_id))
    await callback.answer()

@router.callback_query(UserCallback.filter(F.action == "freeze_reason"))
async def freeze_user_reason(callback: types.CallbackQuery, callback_data: UserCallback, state: FSMContext):
    reason = callback_data.data
    data = await state.get_data()
    user_id = data.get('target_user_id')
    if not user_id:
        await callback.answer("❌ Ошибка", show_alert=True)
        return
    if reason == "Другое":
        await callback.message.edit_text("Введите причину заморозки:", reply_markup=get_back_to_admin_keyboard())
        await state.set_state(AdminStates.waiting_freeze_reason_custom)
        return
    admin_id = callback.from_user.id
    freeze_user(user_id, reason, admin_id)
    log_admin_action(admin_id, 'freeze_user', 'user', user_id, {'reason': reason})
    await callback.answer(f"✅ Пользователь {user_id} заморожен", show_alert=True)
    await callback.message.edit_text(f"❄️ Пользователь заморожен.\nПричина: {reason}", reply_markup=get_back_to_admin_keyboard())
    await state.clear()

@router.message(AdminStates.waiting_freeze_reason_custom)
async def freeze_user_custom_reason(message: types.Message, state: FSMContext):
    data = await state.get_data()
    user_id = data.get('target_user_id')
    if user_id:
        freeze_user(user_id, message.text, message.from_user.id)
        log_admin_action(message.from_user.id, 'freeze_user', 'user', user_id, {'reason': message.text})
        await message.answer(f"✅ Пользователь {user_id} заморожен.\nПричина: {message.text}")
    await state.clear()

@router.callback_query(UserCallback.filter(F.action == "unfreeze"))
async def unfreeze_user_handler(callback: types.CallbackQuery, callback_data: UserCallback):
    user_id = callback_data.user_id
    unfreeze_user(user_id)
    log_admin_action(callback.from_user.id, 'unfreeze_user', 'user', user_id)
    await callback.answer(f"✅ Пользователь {user_id} разморожен", show_alert=True)
    await callback.message.edit_text(f"🧊 Пользователь разморожен.", reply_markup=get_back_to_admin_keyboard())

@router.callback_query(AdminCallback.filter(F.action == "list_frozen"))
async def list_frozen(callback: types.CallbackQuery, callback_data: AdminCallback):
    page = callback_data.page
    frozen = get_all_frozen_users()
    if not frozen:
        await callback.message.edit_text("📭 Замороженных пользователей нет.", reply_markup=get_back_to_admin_keyboard())
        await callback.answer()
        return
    total_pages = (len(frozen) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    page = max(1, min(page, total_pages))
    start = (page - 1) * ITEMS_PER_PAGE
    end = start + ITEMS_PER_PAGE
    current = frozen[start:end]

    text = f"❄️ <b>СПИСОК ЗАМОРОЖЕННЫХ</b> (стр. {page}/{total_pages})\n\n"
    for f in current:
        user_id, username, full_name, reason, frozen_at = f
        text += f"❄️ @{username or 'no_username'} (ID: {user_id})\n├─ Причина: {reason}\n├─ Дата: {format_datetime(frozen_at)}\n└─ [🧊 РАЗМОРОЗИТЬ]\n\n"

    keyboard = get_pagination_keyboard(page, total_pages, "list_frozen")
    builder = InlineKeyboardBuilder()
    builder.attach(InlineKeyboardBuilder.from_markup(keyboard))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=AdminCallback(action="users_menu").pack()))
    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()

@router.callback_query(UserCallback.filter(F.action == "give_stars"))
async def give_stars_start(callback: types.CallbackQuery, callback_data: UserCallback, state: FSMContext):
    user_id = callback_data.user_id
    await state.update_data(target_user_id=user_id)
    await callback.message.edit_text(f"⭐ Введите количество виртуальных звёзд для выдачи пользователю {user_id}:", reply_markup=get_back_to_admin_keyboard())
    await state.set_state(AdminStates.waiting_give_stars_amount)
    await callback.answer()

@router.message(AdminStates.waiting_give_stars_amount)
async def process_give_stars(message: types.Message, state: FSMContext):
    try:
        amount = int(message.text)
        if amount <= 0:
            raise ValueError
        data = await state.get_data()
        user_id = data['target_user_id']
        if update_balance(user_id, amount, 'virtual', 'add'):
            log_admin_action(message.from_user.id, 'give_stars', 'user', user_id, {'amount': amount})
            await message.answer(f"✅ Пользователю {user_id} начислено {amount} ⭐")
        else:
            await message.answer("❌ Ошибка начисления")
        await state.clear()
    except ValueError:
        await message.answer("❌ Введите положительное целое число.")

@router.callback_query(UserCallback.filter(F.action == "deduct_stars"))
async def deduct_stars_start(callback: types.CallbackQuery, callback_data: UserCallback, state: FSMContext):
    user_id = callback_data.user_id
    await state.update_data(target_user_id=user_id)
    await callback.message.edit_text(f"📉 Введите количество виртуальных звёзд для списания у пользователя {user_id}:", reply_markup=get_back_to_admin_keyboard())
    await state.set_state(AdminStates.waiting_deduct_stars_amount)
    await callback.answer()

@router.message(AdminStates.waiting_deduct_stars_amount)
async def process_deduct_stars(message: types.Message, state: FSMContext):
    try:
        amount = int(message.text)
        if amount <= 0:
            raise ValueError
        data = await state.get_data()
        user_id = data['target_user_id']
        if update_balance(user_id, amount, 'virtual', 'subtract'):
            log_admin_action(message.from_user.id, 'deduct_stars', 'user', user_id, {'amount': amount})
            await message.answer(f"✅ У пользователя {user_id} списано {amount} ⭐")
        else:
            await message.answer("❌ Недостаточно баланса или ошибка")
        await state.clear()
    except ValueError:
        await message.answer("❌ Введите положительное целое число.")

@router.callback_query(UserCallback.filter(F.action == "change_role"))
async def change_role_start(callback: types.CallbackQuery, callback_data: UserCallback, state: FSMContext):
    user_id = callback_data.user_id
    await state.update_data(target_user_id=user_id)
    text = (
        "👑 Выберите новую роль:\n"
        "1 - user\n2 - agent\n3 - moder\n4 - admin\n5 - tech_admin (только OWNER)\n6 - owner (только OWNER)"
    )
    await callback.message.edit_text(text, reply_markup=get_back_to_admin_keyboard())
    await state.set_state(AdminStates.waiting_change_role)
    await callback.answer()

@router.message(AdminStates.waiting_change_role)
async def process_change_role(message: types.Message, state: FSMContext):
    role_map = {'1': 'user', '2': 'agent', '3': 'moder', '4': 'admin', '5': 'tech_admin', '6': 'owner'}
    if message.text not in role_map:
        await message.answer("❌ Введите число от 1 до 6.")
        return
    new_role = role_map[message.text]
    if new_role in ['tech_admin', 'owner'] and message.from_user.id != OWNER_ID:
        await message.answer("❌ Только владелец может выдавать эту роль.")
        return
    data = await state.get_data()
    user_id = data['target_user_id']
    set_user_role(user_id, new_role)
    log_admin_action(message.from_user.id, 'change_role', 'user', user_id, {'new_role': new_role})
    await message.answer(f"✅ Роль пользователя {user_id} изменена на {new_role}")
    await state.clear()

@router.callback_query(UserCallback.filter(F.action == "view_profile"))
async def view_profile_admin(callback: types.CallbackQuery, callback_data: UserCallback):
    user_id = callback_data.user_id
    user = get_user(user_id)
    if not user:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return
    await show_user_profile(callback.message, user)
    await callback.answer()

# ========== АЧИВКИ ==========
@router.callback_query(AdminCallback.filter(F.action == "achievements_menu"))
async def achievements_menu(callback: types.CallbackQuery):
    await callback.message.edit_text("🏆 <b>УПРАВЛЕНИЕ АЧИВКАМИ</b>", reply_markup=get_achievements_main_keyboard())
    await callback.answer()

@router.callback_query(AdminCallback.filter(F.action == "list_achievements"))
async def list_achievements(callback: types.CallbackQuery, callback_data: AdminCallback):
    page = callback_data.page
    achievements = get_all_achievements()
    if not achievements:
        await callback.message.edit_text("📭 Ачивки не найдены.", reply_markup=get_back_to_admin_keyboard())
        await callback.answer()
        return
    total_pages = (len(achievements) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    page = max(1, min(page, total_pages))
    start = (page - 1) * ITEMS_PER_PAGE
    end = start + ITEMS_PER_PAGE
    current = achievements[start:end]

    text = f"🏆 <b>СПИСОК ДОСТИЖЕНИЙ</b> (стр. {page}/{total_pages})\n\n"
    for ach in current:
        code, name, desc, icon, hidden, created = ach
        count = get_achievement_stats(code)
        text += f"{icon} <b>{name}</b>\n├─ {desc}\n├─ Получили: {count} пользователей\n└─ [✏️] [👤 ВЫДАТЬ] [🗑️ УДАЛИТЬ У ВСЕХ]\n\n"

    keyboard = get_pagination_keyboard(page, total_pages, "list_achievements")
    builder = InlineKeyboardBuilder()
    builder.attach(InlineKeyboardBuilder.from_markup(keyboard))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=AdminCallback(action="achievements_menu").pack()))
    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()

@router.callback_query(AchievementCallback.filter(F.action == "edit"))
async def edit_achievement(callback: types.CallbackQuery, callback_data: AchievementCallback, state: FSMContext):
    code = callback_data.code
    await state.update_data(ach_code=code, edit_page=callback_data.page)
    await callback.message.edit_text(f"✏️ Редактирование ачивки '{code}'\n\nВведите новое название:", reply_markup=get_back_to_admin_keyboard())
    await state.set_state(AdminStates.waiting_ach_name)

@router.callback_query(AchievementCallback.filter(F.action == "award"))
async def award_achievement_to_user(callback: types.CallbackQuery, callback_data: AchievementCallback, state: FSMContext):
    code = callback_data.code
    await state.update_data(ach_code=code, award_page=callback_data.page)
    await callback.message.edit_text(f"👤 Введите ID или @username пользователя для выдачи ачивки '{code}':", reply_markup=get_back_to_admin_keyboard())
    await state.set_state(AdminStates.waiting_ach_user)

@router.callback_query(AchievementCallback.filter(F.action == "delete_global"))
async def delete_achievement_global(callback: types.CallbackQuery, callback_data: AchievementCallback):
    code = callback_data.code
    delete_achievement(code)
    await callback.answer(f"🗑️ Ачивка '{code}' удалена у всех пользователей", show_alert=True)
    await list_achievements(callback, AdminCallback(action="list_achievements", page=callback_data.page))

@router.callback_query(AdminCallback.filter(F.action == "create_achievement"))
async def create_achievement_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Введите код ачивки (латиница, без пробелов):", reply_markup=get_back_to_admin_keyboard())
    await state.set_state(AdminStates.waiting_ach_code)
    await callback.answer()

@router.message(AdminStates.waiting_ach_code)
async def process_ach_code(message: types.Message, state: FSMContext):
    code = message.text.strip()
    await state.update_data(ach_code=code)
    await message.answer("Введите название ачивки:")
    await state.set_state(AdminStates.waiting_ach_name)

@router.message(AdminStates.waiting_ach_name)
async def process_ach_name(message: types.Message, state: FSMContext):
    await state.update_data(ach_name=message.text)
    await message.answer("Введите описание ачивки:")
    await state.set_state(AdminStates.waiting_ach_description)

@router.message(AdminStates.waiting_ach_description)
async def process_ach_description(message: types.Message, state: FSMContext):
    await state.update_data(ach_description=message.text)
    await message.answer("Введите иконку (эмодзи), по умолчанию 🏆:", reply_markup=get_back_to_admin_keyboard())
    await state.set_state(AdminStates.waiting_ach_icon)

@router.message(AdminStates.waiting_ach_icon)
async def process_ach_icon(message: types.Message, state: FSMContext):
    icon = message.text.strip() or '🏆'
    await state.update_data(ach_icon=icon)
    await message.answer("Скрытая? (да/нет):")
    await state.set_state(AdminStates.waiting_ach_hidden)

@router.message(AdminStates.waiting_ach_hidden)
async def process_ach_hidden(message: types.Message, state: FSMContext):
    hidden = message.text.lower() in ['да', 'yes', '1', 'true']
    data = await state.get_data()
    create_achievement(
        code=data['ach_code'],
        name=data['ach_name'],
        description=data['ach_description'],
        icon=data['ach_icon'],
        hidden=hidden
    )
    await message.answer(f"✅ Ачивка '{data['ach_name']}' создана!")
    await state.clear()
    await achievements_menu_custom(message)

@router.callback_query(AdminCallback.filter(F.action == "award_achievement_menu"))
async def award_achievement_menu(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Введите ID или @username пользователя:", reply_markup=get_back_to_admin_keyboard())
    await state.set_state(AdminStates.waiting_ach_user)
    await callback.answer()

@router.message(AdminStates.waiting_ach_user)
async def process_ach_user(message: types.Message, state: FSMContext):
    identifier = message.text.strip()
    user = get_user_by_id_or_username(identifier)
    if not user:
        await message.answer("❌ Пользователь не найден.")
        return
    await state.update_data(ach_user_id=user[1])
    achievements = get_all_achievements()
    text = "🏆 Выберите ачивку для выдачи:\n\n"
    builder = InlineKeyboardBuilder()
    for ach in achievements:
        code, name, desc, icon, hidden, created = ach
        builder.row(InlineKeyboardButton(
            text=f"{icon} {name}",
            callback_data=AchievementCallback(action="award_select", code=code).pack()
        ))
    builder.row(InlineKeyboardButton(text="⬅️ Отмена", callback_data=AdminCallback(action="achievements_menu").pack()))
    await message.answer(text, reply_markup=builder.as_markup())
    await state.set_state(AdminStates.waiting_ach_select)

@router.callback_query(AchievementCallback.filter(F.action == "award_select"))
async def award_achievement_select(callback: types.CallbackQuery, callback_data: AchievementCallback, state: FSMContext):
    code = callback_data.code
    data = await state.get_data()
    user_id = data['ach_user_id']
    if award_achievement(user_id, code):
        await callback.answer("✅ Ачивка выдана!", show_alert=True)
    else:
        await callback.answer("❌ Ошибка или уже есть", show_alert=True)
    await state.clear()
    await achievements_menu(callback)

@router.callback_query(AdminCallback.filter(F.action == "remove_achievement_menu"))
async def remove_achievement_menu(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Введите ID или @username пользователя:", reply_markup=get_back_to_admin_keyboard())
    await state.set_state(AdminStates.waiting_ach_user)
    await callback.answer()

async def achievements_menu_custom(message: types.Message):
    await message.answer("🏆 Управление ачивками", reply_markup=get_achievements_main_keyboard())

# ========== ТЕХНИЧЕСКОЕ (исправлено – время уменьшается) ==========
@router.callback_query(AdminCallback.filter(F.action == "tech_menu"))
async def tech_menu(callback: types.CallbackQuery):
    await callback.message.edit_text("🛠️ <b>ТЕХНИЧЕСКОЕ ОБСЛУЖИВАНИЕ</b>", reply_markup=get_tech_main_keyboard())
    await callback.answer()

@router.callback_query(AdminCallback.filter(F.action == "maintenance_menu"))
async def maintenance_menu(callback: types.CallbackQuery):
    enabled = is_maintenance_mode()
    status = "🟢 ВЫКЛЮЧЕН" if not enabled else "🔴 ВКЛЮЧЕН"
    info = get_maintenance_info()
    reason = info.get('reason', 'Не указана')
    remaining = info.get('remaining', 'не определено')
    text = (
        f"🛠️ <b>РЕЖИМ ТЕХНИЧЕСКИХ РАБОТ</b>\n\n"
        f"Текущий статус: {status}\n\n"
        f"────────────────────\n"
        f"ТЕКУЩИЕ ПАРАМЕТРЫ:\n"
        f"Причина: {reason}\n"
        f"Осталось: {remaining}\n"
        f"────────────────────\n"
    )
    await callback.message.edit_text(text, reply_markup=get_maintenance_keyboard())
    await callback.answer()

@router.callback_query(AdminCallback.filter(F.action == "maintenance_on"))
async def maintenance_on(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Введите причину тех.работ:", reply_markup=get_back_to_admin_keyboard())
    await state.set_state(AdminStates.waiting_maintenance_reason)
    await callback.answer()

@router.message(AdminStates.waiting_maintenance_reason)
async def process_maintenance_reason(message: types.Message, state: FSMContext):
    await state.update_data(reason=message.text)
    await message.answer("Введите время в минутах (целое число):")
    await state.set_state(AdminStates.waiting_maintenance_duration)

@router.message(AdminStates.waiting_maintenance_duration)
async def process_maintenance_duration(message: types.Message, state: FSMContext):
    try:
        duration = int(message.text)
        if duration <= 0:
            raise ValueError
        data = await state.get_data()
        reason = data['reason']
        set_maintenance_mode(True, reason, duration)
        await message.answer(f"🔴 Режим тех.работ включён.\nПричина: {reason}\nВремя: {duration} мин")
        await state.clear()
    except ValueError:
        await message.answer("❌ Введите положительное целое число минут.", reply_markup=get_back_to_admin_keyboard())

@router.callback_query(AdminCallback.filter(F.action == "maintenance_off"))
async def maintenance_off(callback: types.CallbackQuery):
    set_maintenance_mode(False)
    await callback.answer("🟢 Режим тех.работ выключен", show_alert=True)
    await maintenance_menu(callback)

@router.callback_query(AdminCallback.filter(F.action == "backup_menu"))
async def backup_menu(callback: types.CallbackQuery):
    await callback.message.edit_text("💾 <b>БЕКАПЫ</b>", reply_markup=get_backup_menu_keyboard())
    await callback.answer()

@router.callback_query(AdminCallback.filter(F.action == "create_backup"))
async def create_backup_cmd(callback: types.CallbackQuery):
    if not has_access(callback.from_user.id, 'tech_admin'):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    backup_file = create_backup()
    doc = FSInputFile(backup_file)
    await callback.message.answer_document(
        doc,
        caption=f"✅ Бекап создан: {os.path.basename(backup_file)}\nРазмер: {format_file_size(os.path.getsize(backup_file))}"
    )
    await callback.answer()

@router.callback_query(AdminCallback.filter(F.action == "list_backups"))
async def list_backups_cmd(callback: types.CallbackQuery, callback_data: AdminCallback):
    page = callback_data.page
    backups = list_backups()
    if not backups:
        await callback.message.edit_text("📭 Бекапы не найдены.", reply_markup=get_back_to_admin_keyboard())
        await callback.answer()
        return
    total_pages = (len(backups) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    page = max(1, min(page, total_pages))
    start = (page - 1) * ITEMS_PER_PAGE
    end = start + ITEMS_PER_PAGE
    current = backups[start:end]

    text = f"📋 <b>СПИСОК БЕКАПОВ</b> (стр. {page}/{total_pages})\n\n"
    for i, b in enumerate(current, start=start+1):
        text += f"{i}. {b['name']} — {format_file_size(b['size'])} — {format_datetime(b['mtime'])}\n"
        text += f"   [🔄 ВОССТАНОВИТЬ] [🗑️ УДАЛИТЬ]\n\n"

    keyboard = get_pagination_keyboard(page, total_pages, "list_backups")
    builder = InlineKeyboardBuilder()
    builder.attach(InlineKeyboardBuilder.from_markup(keyboard))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=AdminCallback(action="tech_menu").pack()))
    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()

@router.callback_query(BackupCallback.filter(F.action == "restore"))
async def restore_backup_cmd(callback: types.CallbackQuery, callback_data: BackupCallback, state: FSMContext):
    if not has_access(callback.from_user.id, 'tech_admin'):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    filename = callback_data.filename
    filepath = os.path.join(BACKUP_DIR, filename)
    if not os.path.exists(filepath):
        await callback.answer("❌ Файл не найден", show_alert=True)
        return
    await state.update_data(backup_file=filepath, backup_page=callback_data.page)
    await callback.message.edit_text(
        f"⚠️ <b>ВНИМАНИЕ!</b>\n\nВы выбрали: {filename}\n\n"
        f"Восстановление ЗАМЕНИТ текущую базу данных.\n"
        f"Все изменения после создания бекапа будут УТЕРЯНЫ!\n\n"
        f"Введите <code>ДА</code> для подтверждения:",
        reply_markup=get_back_to_admin_keyboard()
    )
    await state.set_state(AdminStates.waiting_restore_confirm)

@router.message(AdminStates.waiting_restore_confirm)
async def confirm_restore(message: types.Message, state: FSMContext):
    if message.text.strip().upper() != "ДА":
        await message.answer("❌ Восстановление отменено.")
        await state.clear()
        return
    data = await state.get_data()
    filepath = data['backup_file']
    if restore_backup(filepath):
        await message.answer("✅ База данных восстановлена из бекапа!")
    else:
        await message.answer("❌ Ошибка восстановления.")
    await state.clear()

@router.callback_query(BackupCallback.filter(F.action == "delete"))
async def delete_backup_cmd(callback: types.CallbackQuery, callback_data: BackupCallback):
    if not has_access(callback.from_user.id, 'tech_admin'):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    filename = callback_data.filename
    filepath = os.path.join(BACKUP_DIR, filename)
    try:
        os.remove(filepath)
        await callback.answer(f"🗑️ Бекап {filename} удалён", show_alert=True)
    except Exception as e:
        logger.error(f"Ошибка удаления бекапа: {e}")
        await callback.answer("❌ Ошибка удаления", show_alert=True)
    await list_backups_cmd(callback, AdminCallback(action="list_backups", page=callback_data.page))

@router.callback_query(AdminCallback.filter(F.action == "clear_cache"))
async def clear_cache_cmd(callback: types.CallbackQuery):
    await invalidate_settings_cache()
    await invalidate_top_cache()
    from utils import cache
    await cache.clear()
    await callback.answer("🧹 Кэш очищен!", show_alert=True)

@router.callback_query(AdminCallback.filter(F.action == "system_status"))
async def system_status(callback: types.CallbackQuery):
    import psutil
    import platform
    from main import bot
    uptime_seconds = (datetime.now() - bot.start_time).seconds if hasattr(bot, 'start_time') else 0
    status_text = (
        f"📊 <b>СТАТУС СИСТЕМЫ</b>\n\n"
        f"├─ Бот: 🟢 РАБОТАЕТ\n"
        f"├─ БД: 🟢 СОЕДИНЕНИЕ\n"
        f"├─ RAM: {psutil.virtual_memory().used / 1024 / 1024:.0f} MB / {psutil.virtual_memory().total / 1024 / 1024:.0f} MB\n"
        f"├─ Uptime: {format_duration(uptime_seconds)}\n"
        f"└─ Платформа: {platform.system()} {platform.release()}"
    )
    await callback.message.edit_text(status_text, reply_markup=get_back_to_admin_keyboard())
    await callback.answer()

# ========== РАССЫЛКА ==========
@router.callback_query(AdminCallback.filter(F.action == "mailing_menu"))
async def mailing_menu(callback: types.CallbackQuery):
    await callback.message.edit_text("📢 <b>РАССЫЛКА</b>", reply_markup=get_mailing_main_keyboard())
    await callback.answer()

@router.callback_query(AdminCallback.filter(F.action == "create_mailing"))
async def create_mailing_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "📢 <b>СОЗДАНИЕ РАССЫЛКИ</b>\n\n"
        "1️⃣ КОМУ ОТПРАВЛЯЕМ:\n"
        "Выберите аудиторию:",
        reply_markup=get_mailing_filter_keyboard()
    )
    await state.set_state(AdminStates.waiting_generic_text)
    await callback.answer()

@router.callback_query(AdminCallback.filter(F.action.startswith("mailing_filter_")))
async def mailing_filter_choice(callback: types.CallbackQuery, callback_data: AdminCallback, state: FSMContext):
    filter_type = callback_data.action.replace("mailing_filter_", "")
    await state.update_data(mailing_filter=filter_type)
    await callback.message.edit_text(
        "2️⃣ СОДЕРЖИМОЕ:\n\n"
        "📝 Введите текст сообщения:",
        reply_markup=get_back_to_admin_keyboard()
    )
    await state.set_state(AdminStates.waiting_mailing_text)
    await callback.answer()

@router.message(AdminStates.waiting_mailing_text)
async def process_mailing_text(message: types.Message, state: FSMContext):
    await state.update_data(mailing_text=message.text)
    await message.answer(
        "📎 Прикрепите медиа (фото, видео, GIF, стикер) или отправьте /skip",
        reply_markup=get_back_to_admin_keyboard()
    )
    await state.set_state(AdminStates.waiting_mailing_media)

@router.message(AdminStates.waiting_mailing_media, F.photo | F.video | F.animation | F.sticker)
async def process_mailing_media(message: types.Message, state: FSMContext):
    if message.photo:
        media = ('photo', message.photo[-1].file_id)
    elif message.video:
        media = ('video', message.video.file_id)
    elif message.animation:
        media = ('animation', message.animation.file_id)
    elif message.sticker:
        media = ('sticker', message.sticker.file_id)
    else:
        media = None
    await state.update_data(mailing_media=media)
    await message.answer("➕ Введите текст кнопки (или /skip):")
    await state.set_state(AdminStates.waiting_mailing_button_text)

@router.message(AdminStates.waiting_mailing_media, Command("skip"))
async def skip_mailing_media(message: types.Message, state: FSMContext):
    await state.update_data(mailing_media=None)
    await message.answer("➕ Введите текст кнопки (или /skip):")
    await state.set_state(AdminStates.waiting_mailing_button_text)

@router.message(AdminStates.waiting_mailing_button_text, Command("skip"))
async def skip_mailing_button(message: types.Message, state: FSMContext):
    await state.update_data(mailing_button=None)
    await preview_mailing(message, state)

@router.message(AdminStates.waiting_mailing_button_text)
async def process_mailing_button_text(message: types.Message, state: FSMContext):
    await state.update_data(mailing_button_text=message.text)
    await message.answer("🔗 Введите URL для кнопки:")
    await state.set_state(AdminStates.waiting_mailing_button_url)

@router.message(AdminStates.waiting_mailing_button_url)
async def process_mailing_button_url(message: types.Message, state: FSMContext):
    url = message.text
    data = await state.get_data()
    button = (data.get('mailing_button_text'), url)
    await state.update_data(mailing_button=button)
    await preview_mailing(message, state)

async def preview_mailing(message: types.Message, state: FSMContext):
    data = await state.get_data()
    filter_type = data.get('mailing_filter')
    text = data.get('mailing_text')
    media = data.get('mailing_media')
    button = data.get('mailing_button')

    if filter_type == 'all':
        users = get_all_users()
        count = len(users)
    elif filter_type == 'active':
        active, _ = get_users_by_activity(7)
        count = len(active)
    elif filter_type == 'inactive':
        _, inactive = get_users_by_activity(30)
        count = len(inactive)
    elif filter_type == 'top':
        top = get_top_buyers_no_admins(10)
        count = len(top)
    elif filter_type == 'test':
        count = 1
    else:
        count = 0

    preview = f"📢 <b>ПРЕДПРОСМОТР РАССЫЛКИ</b>\n\n"
    preview += f"КОМУ: {filter_type} ({count} чел.)\n\n"
    preview += f"ТЕКСТ:\n━━━━━━━━━━━━━━━━━━━━\n{text}\n━━━━━━━━━━━━━━━━━━━━\n\n"
    preview += f"📊 СТАТИСТИКА:\n├─ Длина текста: {len(text)} символов\n├─ Есть медиа: {'Да' if media else 'Нет'}\n└─ Примерное время отправки: {count//30 + 1} сек"
    await message.answer(preview, reply_markup=get_mailing_preview_keyboard())

@router.callback_query(AdminCallback.filter(F.action == "mailing_send"))
async def mailing_send(callback: types.CallbackQuery, state: FSMContext):
    from main import bot
    data = await state.get_data()
    filter_type = data.get('mailing_filter')
    text = data.get('mailing_text')
    media = data.get('mailing_media')
    button = data.get('mailing_button')

    if filter_type == 'all':
        users = get_all_users()
    elif filter_type == 'active':
        active, _ = get_users_by_activity(7)
        users = active
    elif filter_type == 'inactive':
        _, inactive = get_users_by_activity(30)
        users = inactive
    elif filter_type == 'top':
        top = get_top_buyers_no_admins(10)
        users = [(u[0], u[1], u[2]) for u in top]
    elif filter_type == 'test':
        users = [(callback.from_user.id, None, None)]
    else:
        users = []

    success = 0
    fail = 0

    for user in users:
        user_id = user[0] if isinstance(user, tuple) else user[0]
        try:
            if media:
                media_type, file_id = media
                if media_type == 'photo':
                    await bot.send_photo(user_id, file_id, caption=text)
                elif media_type == 'video':
                    await bot.send_video(user_id, file_id, caption=text)
                elif media_type == 'animation':
                    await bot.send_animation(user_id, file_id, caption=text)
                elif media_type == 'sticker':
                    await bot.send_sticker(user_id, file_id)
                    if text:
                        await bot.send_message(user_id, text)
            else:
                await bot.send_message(user_id, text)
            success += 1
        except Exception as e:
            logger.error(f"Ошибка отправки {user_id}: {e}")
            fail += 1

    await callback.message.edit_text(
        f"✅ РАССЫЛКА ЗАВЕРШЕНА\n\n"
        f"📊 РЕЗУЛЬТАТЫ:\n"
        f"├─ Всего: {len(users)}\n"
        f"├─ Доставлено: {success}\n"
        f"└─ Ошибок: {fail}"
    )
    await state.clear()
    await callback.answer()

@router.callback_query(AdminCallback.filter(F.action == "mailing_edit"))
async def mailing_edit(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "✏️ Редактирование рассылки\n\nВведите новый текст:",
        reply_markup=get_back_to_admin_keyboard()
    )
    await state.set_state(AdminStates.waiting_mailing_text)
    await callback.answer()

@router.callback_query(AdminCallback.filter(F.action == "mailing_stats"))
async def mailing_stats(callback: types.CallbackQuery, callback_data: AdminCallback):
    page = callback_data.page
    await callback.message.edit_text(
        "📊 Статистика рассылок\n\nВ разработке.",
        reply_markup=get_back_to_admin_keyboard()
    )
    await callback.answer()

# ========== ЗАКАЗЫ ==========
@router.callback_query(AdminCallback.filter(F.action == "orders_menu"))
async def orders_menu(callback: types.CallbackQuery):
    orders = get_pending_orders()
    count = len(orders)
    text = f"📦 <b>ЗАКАЗЫ</b>\n\nОжидают подтверждения: {count}"
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📋 Показать все", callback_data=AdminCallback(action="list_orders").pack()))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=AdminCallback(action="main").pack()))
    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()

@router.callback_query(AdminCallback.filter(F.action == "list_orders"))
async def list_orders(callback: types.CallbackQuery):
    orders = get_pending_orders()
    if not orders:
        await callback.message.edit_text("✅ Нет pending заявок.", reply_markup=get_back_to_admin_keyboard())
        await callback.answer()
        return
    for order in orders:
        order_id, user_id_db, amount, recipient, screenshot, status, total_price, promocode_id, discount, created_at, _, buyer_username = order
        final_price = total_price - (discount or 0)
        order_text = (
            f"🆔 <b>Заявка #{order_id}</b>\n\n"
            f"👤 Покупатель: @{buyer_username}\n"
            f"⭐ Количество: {amount} звёзд\n"
            f"💰 Сумма: {final_price:.2f}₽\n"
            f"🎯 Получатель: {recipient}\n"
            f"📅 Дата: {format_datetime(created_at)}"
        )
        try:
            await callback.message.answer(order_text)
            if os.path.exists(screenshot):
                photo = FSInputFile(screenshot)
                await callback.message.answer_photo(
                    photo,
                    caption=f"Заявка #{order_id}",
                    reply_markup=get_order_action_keyboard(order_id)
                )
            else:
                await callback.message.answer(
                    "⚠️ Скриншот не найден",
                    reply_markup=get_order_action_keyboard(order_id)
                )
        except Exception as e:
            logger.error(f"Ошибка отправки заявки {order_id}: {e}")
            await callback.message.answer(
                f"❌ Ошибка загрузки заявки #{order_id}",
                reply_markup=get_order_action_keyboard(order_id)
            )
    await callback.answer()

# ========== СТАТИСТИКА ==========
@router.callback_query(AdminCallback.filter(F.action == "stats_menu"))
async def stats_menu(callback: types.CallbackQuery):
    revenue_day = get_revenue_for_period(1)
    revenue_week = get_revenue_for_period(7)
    revenue_month = get_revenue_for_period(30)
    active_users_day = get_active_users_count(1)
    active_users_week = get_active_users_count(7)
    active_users_month = get_active_users_count(30)
    avg_check_day = get_average_check(1)
    avg_check_week = get_average_check(7)
    avg_check_month = get_average_check(30)
    top_buyers = get_top_buyers_no_admins(5)
    users_by_role = count_users_by_role()
    stats_text = "📊 <b>СТАТИСТИКА БОТА</b>\n\n"
    stats_text += "💰 <b>Выручка:</b>\n"
    stats_text += f"• За день: {revenue_day:.2f}₽\n"
    stats_text += f"• За неделю: {revenue_week:.2f}₽\n"
    stats_text += f"• За месяц: {revenue_month:.2f}₽\n\n"
    stats_text += "👥 <b>Активные пользователи:</b>\n"
    stats_text += f"• За день: {active_users_day}\n"
    stats_text += f"• За неделю: {active_users_week}\n"
    stats_text += f"• За месяц: {active_users_month}\n\n"
    stats_text += "🧾 <b>Средний чек:</b>\n"
    stats_text += f"• За день: {avg_check_day:.2f}₽\n"
    stats_text += f"• За неделю: {avg_check_week:.2f}₽\n"
    stats_text += f"• За месяц: {avg_check_month:.2f}₽\n\n"
    stats_text += "👥 <b>Пользователи по ролям:</b>\n"
    for role, count in users_by_role.items():
        stats_text += f"• {get_role_display(role)}: {count}\n"
    stats_text += "\n🏆 <b>Топ-5 покупателей (без админов):</b>\n"
    if top_buyers:
        for i, (username, fullname, total) in enumerate(top_buyers, 1):
            stats_text += f"{i}. @{username or 'Аноним'}: {total:.2f}₽\n"
    else:
        stats_text += "• Нет данных\n"
    await callback.message.edit_text(stats_text, reply_markup=get_back_to_admin_keyboard())
    await callback.answer()

# ========== НАСТРОЙКИ ==========
@router.callback_query(AdminCallback.filter(F.action == "settings_menu"))
async def settings_menu(callback: types.CallbackQuery):
    await callback.message.edit_text("⚙️ <b>НАСТРОЙКИ</b>", reply_markup=get_settings_main_keyboard())
    await callback.answer()

@router.callback_query(AdminCallback.filter(F.action == "settings_general"))
async def settings_general(callback: types.CallbackQuery):
    text = (
        "⚙️ <b>Общие настройки</b>\n\n"
        "• Курс обмена и комиссии – в разделе Экономика\n"
        "• Реферальные уровни – в разделе Настройки -> Рефералы\n"
        "• Авто-бекапы – в разделе Техническое\n"
    )
    await callback.message.edit_text(text, reply_markup=get_back_to_admin_keyboard())
    await callback.answer()

@router.callback_query(AdminCallback.filter(F.action == "settings_games"))
async def settings_games(callback: types.CallbackQuery):
    text = (
        "🎮 <b>Настройки игр</b>\n\n"
        f"• Мины: выигрыш +{MINES_GAME_WIN_REWARD}⭐, проигрыш -{MINES_GAME_LOSE_PENALTY}⭐\n"
        f"• Казино: ставки {', '.join(map(str, CASINO_BET_AMOUNTS))}⭐, шанс {CASINO_WIN_CHANCE*100}%, множитель {CASINO_WIN_MULTIPLIER}x\n\n"
        "Редактирование через config.py (требует перезапуска)"
    )
    await callback.message.edit_text(text, reply_markup=get_back_to_admin_keyboard())
    await callback.answer()

@router.callback_query(AdminCallback.filter(F.action == "settings_referrals"))
async def settings_referrals(callback: types.CallbackQuery):
    levels = get_referral_levels()
    text = "🔗 <b>Реферальные уровни</b>\n\n"
    for level in levels:
        text += f"• {level['name']}: {level['min']}-{level['max'] if level['max']!=999999 else '∞'} рефералов, {level['percent']}%\n"
    text += "\nРедактирование через JSON в БД (в разработке)"
    await callback.message.edit_text(text, reply_markup=get_back_to_admin_keyboard())
    await callback.answer()

# ========== ЖУРНАЛ ==========
@router.callback_query(AdminCallback.filter(F.action == "logs_menu"))
async def logs_menu(callback: types.CallbackQuery):
    await callback.message.edit_text("📜 <b>ЖУРНАЛ ДЕЙСТВИЙ АДМИНИСТРАЦИИ</b>", reply_markup=get_logs_filter_keyboard())
    await callback.answer()

async def show_logs(callback: types.CallbackQuery, logs: list, page: int):
    items_per_page = 10
    total_pages = (len(logs) + items_per_page - 1) // items_per_page
    page = max(1, min(page, total_pages))
    start = (page - 1) * items_per_page
    end = start + items_per_page
    current = logs[start:end]

    text = f"📜 <b>ЖУРНАЛ ДЕЙСТВИЙ</b> (стр. {page}/{total_pages})\n\n"
    for log in current:
        log_id, admin_id, admin_username, action, target_type, target_id, details, ip, created_at = log
        time = format_datetime(created_at)
        admin = f"@{admin_username}" if admin_username else f"id{admin_id}"
        text += f"[{time}] {admin}\n"
        text += f"   └─ {action}"
        if target_type:
            text += f" {target_type}"
            if target_id:
                text += f" #{target_id}"
        if details:
            try:
                d = json.loads(details)
                text += f" | {d}"
            except:
                pass
        text += "\n\n"

    keyboard = get_pagination_keyboard(page, total_pages, "logs_reset")
    builder = InlineKeyboardBuilder()
    builder.attach(InlineKeyboardBuilder.from_markup(keyboard))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=AdminCallback(action="logs_menu").pack()))
    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()

@router.callback_query(AdminCallback.filter(F.action == "logs_reset"))
async def logs_reset(callback: types.CallbackQuery, callback_data: AdminCallback):
    page = callback_data.page
    logs = get_admin_logs(days=7, limit=50)
    await show_logs(callback, logs, page)

@router.callback_query(AdminCallback.filter(F.action == "logs_filter_admin"))
async def logs_filter_admin(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "Введите ID или @username администратора:",
        reply_markup=get_back_to_admin_keyboard()
    )
    await state.set_state(AdminStates.waiting_user_search)
    await callback.answer()

@router.callback_query(AdminCallback.filter(F.action == "logs_filter_action"))
async def logs_filter_action(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "Введите тип действия (например: approve_order, freeze_user):",
        reply_markup=get_back_to_admin_keyboard()
    )
    await state.set_state(AdminStates.waiting_generic_text)
    await callback.answer()

@router.callback_query(AdminCallback.filter(F.action == "logs_filter_date"))
async def logs_filter_date(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "Введите количество дней для анализа (по умолчанию 7):",
        reply_markup=get_back_to_admin_keyboard()
    )
    await state.set_state(AdminStates.waiting_generic_number)
    await callback.answer()

@router.callback_query(AdminCallback.filter(F.action == "logs_export"))
async def logs_export(callback: types.CallbackQuery, callback_data: AdminCallback):
    logs = get_admin_logs(days=7, limit=1000)
    filename = f"admin_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(filename, 'w', encoding='utf-8') as f:
        for log in logs:
            f.write(str(log) + '\n')
    doc = FSInputFile(filename)
    await callback.message.answer_document(doc, caption="📥 Экспорт журнала действий")
    os.remove(filename)
    await callback.answer()

# ========== КОМАНДЫ АДМИНИСТРАТОРА (В ТЕКСТОВЫХ СООБЩЕНИЯХ) ==========
@router.message(Command("backup"))
async def cmd_backup(message: types.Message):
    if not has_access(message.from_user.id, 'tech_admin'):
        await message.answer("⛔ Нет доступа")
        return
    backup_file = create_backup()
    doc = FSInputFile(backup_file)
    await message.answer_document(
        doc,
        caption=f"✅ Бекап создан: {os.path.basename(backup_file)}\nРазмер: {format_file_size(os.path.getsize(backup_file))}"
    )

@router.message(Command("restore"))
async def cmd_restore(message: types.Message, state: FSMContext):
    if not has_access(message.from_user.id, 'tech_admin'):
        await message.answer("⛔ Нет доступа")
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("❌ Использование: /restore имя_файла.db")
        return
    filename = args[1]
    filepath = os.path.join(BACKUP_DIR, filename)
    if not os.path.exists(filepath):
        await message.answer("❌ Файл не найден")
        return
    await state.update_data(backup_file=filepath)
    await message.answer(
        f"⚠️ <b>ВНИМАНИЕ!</b>\n\nВосстановление ЗАМЕНИТ текущую базу данных.\n"
        f"Все изменения будут УТЕРЯНЫ!\n\nВведите <code>ДА</code> для подтверждения:",
        reply_markup=get_back_to_admin_keyboard()
    )
    await state.set_state(AdminStates.waiting_restore_confirm)

@router.message(Command("teh_on"))
async def cmd_teh_on(message: types.Message, state: FSMContext):
    if not has_access(message.from_user.id, 'tech_admin'):
        await message.answer("⛔ Нет доступа")
        return
    await message.answer("Введите причину тех.работ:")
    await state.set_state(AdminStates.waiting_maintenance_reason)

@router.message(Command("teh_off"))
async def cmd_teh_off(message: types.Message):
    if not has_access(message.from_user.id, 'tech_admin'):
        await message.answer("⛔ Нет доступа")
        return
    set_maintenance_mode(False)
    await message.answer("🟢 Режим тех.работ выключен")

@router.message(Command("freeze"))
async def cmd_freeze(message: types.Message, state: FSMContext):
    if not has_access(message.from_user.id, 'admin'):
        await message.answer("⛔ Нет доступа")
        return
    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        await message.answer("❌ Использование: /freeze @username/id причина")
        return
    identifier = args[1]
    reason = args[2]
    user = get_user_by_id_or_username(identifier)
    if not user:
        await message.answer("❌ Пользователь не найден")
        return
    user_id = user[1]
    freeze_user(user_id, reason, message.from_user.id)
    log_admin_action(message.from_user.id, 'freeze_user', 'user', user_id, {'reason': reason})
    await message.answer(f"✅ Пользователь {identifier} заморожен")

@router.message(Command("unfreeze"))
async def cmd_unfreeze(message: types.Message):
    if not has_access(message.from_user.id, 'admin'):
        await message.answer("⛔ Нет доступа")
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("❌ Использование: /unfreeze @username/id")
        return
    identifier = args[1]
    user = get_user_by_id_or_username(identifier)
    if not user:
        await message.answer("❌ Пользователь не найден")
        return
    user_id = user[1]
    unfreeze_user(user_id)
    log_admin_action(message.from_user.id, 'unfreeze_user', 'user', user_id)
    await message.answer(f"✅ Пользователь {identifier} разморожен")

@router.message(Command("givestars"))
async def cmd_givestars(message: types.Message):
    if not has_access(message.from_user.id, 'tech_admin'):
        await message.answer("⛔ Нет доступа")
        return
    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        await message.answer("❌ Использование: /givestars сумма @username/id")
        return
    try:
        amount = int(args[1])
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Сумма должна быть положительным числом")
        return
    identifier = args[2]
    user = get_user_by_id_or_username(identifier)
    if not user:
        await message.answer("❌ Пользователь не найден")
        return
    user_id = user[1]
    if update_balance(user_id, amount, 'virtual', 'add'):
        log_admin_action(message.from_user.id, 'give_stars', 'user', user_id, {'amount': amount})
        await message.answer(f"✅ Пользователю {identifier} начислено {amount} ⭐")
    else:
        await message.answer("❌ Ошибка начисления")

@router.message(Command("delstars"))
async def cmd_delstars(message: types.Message):
    if not has_access(message.from_user.id, 'tech_admin'):
        await message.answer("⛔ Нет доступа")
        return
    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        await message.answer("❌ Использование: /delstars сумма @username/id")
        return
    try:
        amount = int(args[1])
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Сумма должна быть положительным числом")
        return
    identifier = args[2]
    user = get_user_by_id_or_username(identifier)
    if not user:
        await message.answer("❌ Пользователь не найден")
        return
    user_id = user[1]
    if update_balance(user_id, amount, 'virtual', 'subtract'):
        log_admin_action(message.from_user.id, 'deduct_stars', 'user', user_id, {'amount': amount})
        await message.answer(f"✅ У пользователя {identifier} списано {amount} ⭐")
    else:
        await message.answer("❌ Недостаточно баланса или ошибка")

@router.message(Command("checkbalance"))
async def cmd_checkbalance(message: types.Message):
    if not has_access(message.from_user.id, 'tech_admin'):
        await message.answer("⛔ Нет доступа")
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("❌ Использование: /checkbalance @username/id")
        return
    identifier = args[1]
    user = get_user_by_id_or_username(identifier)
    if not user:
        await message.answer("❌ Пользователь не найден")
        return
    user_id = user[1]
    username = user[2] or "без юзернейма"
    virtual_balance = user[5]
    await message.answer(f"👤 @{username}\n🎮 Виртуальный баланс: {virtual_balance} ⭐")

@router.message(Command("addagent"))
async def cmd_addagent(message: types.Message):
    if not has_access(message.from_user.id, 'tech_admin'):
        await message.answer("⛔ Нет доступа")
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("❌ Использование: /addagent @username/id")
        return
    identifier = args[1]
    user = get_user_by_id_or_username(identifier)
    if not user:
        await message.answer("❌ Пользователь не найден")
        return
    user_id = user[1]
    set_user_role(user_id, 'agent')
    log_admin_action(message.from_user.id, 'add_role', 'user', user_id, {'role': 'agent'})
    await message.answer(f"✅ Пользователю {identifier} выдана роль агента")

@router.message(Command("addmoder"))
async def cmd_addmoder(message: types.Message):
    if not has_access(message.from_user.id, 'tech_admin'):
        await message.answer("⛔ Нет доступа")
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("❌ Использование: /addmoder @username/id")
        return
    identifier = args[1]
    user = get_user_by_id_or_username(identifier)
    if not user:
        await message.answer("❌ Пользователь не найден")
        return
    user_id = user[1]
    set_user_role(user_id, 'moder')
    log_admin_action(message.from_user.id, 'add_role', 'user', user_id, {'role': 'moder'})
    await message.answer(f"✅ Пользователю {identifier} выдана роль модератора")

@router.message(Command("addadmin"))
async def cmd_addadmin(message: types.Message):
    if not has_access(message.from_user.id, 'tech_admin'):
        await message.answer("⛔ Нет доступа")
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("❌ Использование: /addadmin @username/id")
        return
    identifier = args[1]
    user = get_user_by_id_or_username(identifier)
    if not user:
        await message.answer("❌ Пользователь не найден")
        return
    user_id = user[1]
    set_user_role(user_id, 'admin')
    log_admin_action(message.from_user.id, 'add_role', 'user', user_id, {'role': 'admin'})
    await message.answer(f"✅ Пользователю {identifier} выдана роль админа")

@router.message(Command("delrole"))
async def cmd_delrole(message: types.Message):
    if not has_access(message.from_user.id, 'tech_admin'):
        await message.answer("⛔ Нет доступа")
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("❌ Использование: /delrole @username/id")
        return
    identifier = args[1]
    user = get_user_by_id_or_username(identifier)
    if not user:
        await message.answer("❌ Пользователь не найден")
        return
    user_id = user[1]
    set_user_role(user_id, 'user')
    log_admin_action(message.from_user.id, 'remove_role', 'user', user_id)
    await message.answer(f"✅ Роль пользователя {identifier} сброшена до user")

@router.message(Command("warn"))
async def cmd_warn(message: types.Message):
    if not has_access(message.from_user.id, 'moder'):
        await message.answer("⛔ Нет доступа")
        return
    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        await message.answer("❌ Использование: /warn @username/id причина")
        return
    identifier = args[1]
    reason = args[2]
    user = get_user_by_id_or_username(identifier)
    if not user:
        await message.answer("❌ Пользователь не найден")
        return
    user_id = user[1]
    add_warn(user_id, reason, message.from_user.id)
    log_admin_action(message.from_user.id, 'warn', 'user', user_id, {'reason': reason})
    await message.answer(f"⚠️ Пользователю {identifier} выдано предупреждение")

@router.message(Command("warnlist"))
async def cmd_warnlist(message: types.Message):
    if not has_access(message.from_user.id, 'moder'):
        await message.answer("⛔ Нет доступа")
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("❌ Использование: /warnlist @username/id")
        return
    identifier = args[1]
    user = get_user_by_id_or_username(identifier)
    if not user:
        await message.answer("❌ Пользователь не найден")
        return
    user_id = user[1]
    warns = get_warns(user_id)
    if not warns:
        await message.answer(f"У {identifier} нет предупреждений.")
        return
    text = f"⚠️ Предупреждения {identifier}:\n\n"
    for warn in warns:
        warn_id, _, reason, created_at, mod_id = warn
        mod = get_user(mod_id)
        mod_name = mod[3] if mod else "Неизвестно"
        text += f"ID: {warn_id} | {format_datetime(created_at)}\nМодератор: {mod_name}\nПричина: {reason}\n\n"
    await message.answer(text)

@router.message(Command("unwarn"))
async def cmd_unwarn(message: types.Message):
    if not has_access(message.from_user.id, 'admin'):
        await message.answer("⛔ Нет доступа")
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("❌ Использование: /unwarn @username/id")
        return
    identifier = args[1]
    user = get_user_by_id_or_username(identifier)
    if not user:
        await message.answer("❌ Пользователь не найден")
        return
    user_id = user[1]
    warns = get_warns(user_id)
    if not warns:
        await message.answer(f"У {identifier} нет предупреждений.")
        return
    last_warn_id = warns[0][0]
    remove_warn(last_warn_id)
    log_admin_action(message.from_user.id, 'unwarn', 'user', user_id)
    await message.answer(f"✅ Снято последнее предупреждение с {identifier}")

@router.message(Command("ban"))
async def cmd_ban(message: types.Message):
    if not has_access(message.from_user.id, 'admin'):
        await message.answer("⛔ Нет доступа")
        return
    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        await message.answer("❌ Использование: /ban @username/id причина")
        return
    identifier = args[1]
    reason = args[2]
    user = get_user_by_id_or_username(identifier)
    if not user:
        await message.answer("❌ Пользователь не найден")
        return
    user_id = user[1]
    add_ban(user_id, reason, message.from_user.id)
    log_admin_action(message.from_user.id, 'ban', 'user', user_id, {'reason': reason})
    await message.answer(f"🚫 Пользователь {identifier} забанен")

@router.message(Command("unban"))
async def cmd_unban(message: types.Message):
    if not has_access(message.from_user.id, 'admin'):
        await message.answer("⛔ Нет доступа")
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("❌ Использование: /unban @username/id")
        return
    identifier = args[1]
    user = get_user_by_id_or_username(identifier)
    if not user:
        await message.answer("❌ Пользователь не найден")
        return
    user_id = user[1]
    remove_ban(user_id)
    log_admin_action(message.from_user.id, 'unban', 'user', user_id)
    await message.answer(f"✅ Пользователь {identifier} разбанен")

@router.message(Command("tempban"))
async def cmd_tempban(message: types.Message):
    if not has_access(message.from_user.id, 'admin'):
        await message.answer("⛔ Нет доступа")
        return
    args = message.text.split(maxsplit=3)
    if len(args) < 4:
        await message.answer("❌ Использование: /tempban @username/id часы причина")
        return
    identifier = args[1]
    try:
        hours = int(args[2])
    except ValueError:
        await message.answer("❌ Время должно быть числом")
        return
    reason = args[3]
    user = get_user_by_id_or_username(identifier)
    if not user:
        await message.answer("❌ Пользователь не найден")
        return
    user_id = user[1]
    banned_until = datetime.now() + timedelta(hours=hours)
    add_ban(user_id, reason, message.from_user.id, banned_until)
    log_admin_action(message.from_user.id, 'tempban', 'user', user_id, {'hours': hours, 'reason': reason})
    await message.answer(f"🚫 Пользователь {identifier} забанен на {hours} часов")

@router.message(Command("banlist"))
async def cmd_banlist(message: types.Message):
    if not has_access(message.from_user.id, 'admin'):
        await message.answer("⛔ Нет доступа")
        return
    bans = get_all_bans()
    if not bans:
        await message.answer("📭 Список банов пуст.")
        return
    text = "🚫 <b>Список забаненных пользователей:</b>\n\n"
    for ban in bans:
        ban_id, user_id, reason, banned_at, banned_until, mod_id = ban
        user = get_user(user_id)
        username = user[2] if user else "Неизвестно"
        text += f"👤 @{username} (ID: {user_id})\n"
        text += f"📅 Забанен: {format_datetime(banned_at)}\n"
        text += f"📝 Причина: {reason}\n"
        if banned_until:
            text += f"⏰ Истекает: {format_datetime(banned_until)}\n"
        else:
            text += f"⏰ Навсегда\n"
        text += "\n"
    await message.answer(text)

@router.message(Command("news"))
async def cmd_news(message: types.Message):
    if not has_access(message.from_user.id, 'admin'):
        await message.answer("⛔ Нет доступа")
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("❌ Использование: /news текст новости")
        return
    news_text = args[1]
    users = get_all_users()
    success = 0
    fail = 0
    from main import bot
    for user in users:
        try:
            await bot.send_message(user[0], f"📢 <b>Новости:</b>\n\n{news_text}")
            success += 1
        except Exception:
            fail += 1
    await message.answer(f"✅ Рассылка завершена!\nОтправлено: {success}\nНе доставлено: {fail}")

@router.message(Command("addpromo"))
async def cmd_addpromo(message: types.Message, state: FSMContext):
    if not has_access(message.from_user.id, 'tech_admin'):
        await message.answer("⛔ Нет доступа")
        return
    args = message.text.split(maxsplit=3)
    if len(args) < 4:
        await message.answer("❌ Использование: /addpromo код скидка% активации")
        return
    code = args[1].upper()
    try:
        discount = int(args[2])
        max_uses = int(args[3])
    except ValueError:
        await message.answer("❌ Скидка и активации должны быть числами")
        return
    create_promocode(code, discount, max_uses)
    await message.answer(f"✅ Промокод {code} создан!")

@router.message(Command("helpadmin"))
async def cmd_helpadmin(message: types.Message):
    if not has_access(message.from_user.id, 'tech_admin'):
        await message.answer("⛔ Нет доступа")
        return
    text = (
        "📋 <b>Команды для администрации</b>\n\n"
        "👥 <b>Управление ролями:</b>\n"
        "/addagent @username\n"
        "/addmoder @username\n"
        "/addadmin @username\n"
        "/delrole @username\n\n"
        "⚠️ <b>Варны и баны:</b>\n"
        "/warn @username причина\n"
        "/warnlist @username\n"
        "/unwarn @username\n"
        "/ban @username причина\n"
        "/tempban @username часы причина\n"
        "/unban @username\n"
        "/banlist\n\n"
        "🎮 <b>Управление балансом:</b>\n"
        "/givestars сумма @username\n"
        "/delstars сумма @username\n"
        "/checkbalance @username\n\n"
        "📊 <b>Статистика:</b>\n"
        "/orders - Показать заявки\n"
        "/stats - Статистика бота\n"
        "/tickets - Открытые тикеты\n"
        "/ticket ID - Инфо о тикете\n"
        "/answer ID текст - Ответить в тикет\n"
        "/creport ID - Закрыть тикет\n\n"
        "📢 <b>Рассылка:</b>\n"
        "/news текст\n\n"
        "🎁 <b>Промокоды:</b>\n"
        "/addpromo код % активации\n\n"
        "🛠️ <b>Техническое:</b>\n"
        "/backup - Создать бекап\n"
        "/restore имя_файла.db - Восстановить\n"
        "/teh_on - Включить тех.работы\n"
        "/teh_off - Выключить тех.работы\n"
        "/freeze @username причина - Заморозить\n"
        "/unfreeze @username - Разморозить\n\n"
        "👨‍💼 <b>Администрация:</b>\n"
        "/staff - Список администрации\n"
        "/helpadmin - Эта справка"
    )
    await message.answer(text)

@router.message(Command("orders"))
async def cmd_orders(message: types.Message):
    if not has_access(message.from_user.id, 'admin'):
        await message.answer("⛔ Нет доступа")
        return
    orders = get_pending_orders()
    if not orders:
        await message.answer("✅ Нет pending заявок.")
        return
    for order in orders:
        order_id, user_id, amount, recipient, screenshot, status, total_price, promo_id, discount, created_at, _, buyer_username = order
        final_price = total_price - (discount or 0)
        text = f"🆔 <b>Заявка #{order_id}</b>\n\n👤 Покупатель: @{buyer_username}\n⭐ Количество: {amount} звёзд\n💰 Сумма: {final_price:.2f}₽\n🎯 Получатель: {recipient}\n📅 Дата: {format_datetime(created_at)}"
        await message.answer(text)
        if os.path.exists(screenshot):
            photo = FSInputFile(screenshot)
            await message.answer_photo(photo, caption=f"Заявка #{order_id}", reply_markup=get_order_action_keyboard(order_id))
        else:
            await message.answer("⚠️ Скриншот не найден", reply_markup=get_order_action_keyboard(order_id))

@router.message(Command("stats"))
async def cmd_stats(message: types.Message):
    if not has_access(message.from_user.id, 'admin'):
        await message.answer("⛔ Нет доступа")
        return
    revenue_day = get_revenue_for_period(1)
    revenue_week = get_revenue_for_period(7)
    revenue_month = get_revenue_for_period(30)
    active_day = get_active_users_count(1)
    active_week = get_active_users_count(7)
    active_month = get_active_users_count(30)
    avg_day = get_average_check(1)
    avg_week = get_average_check(7)
    avg_month = get_average_check(30)
    top = get_top_buyers_no_admins(5)
    text = (
        f"📊 <b>Статистика бота</b>\n\n"
        f"💰 <b>Выручка:</b>\n"
        f"├─ День: {revenue_day:.2f}₽\n"
        f"├─ Неделя: {revenue_week:.2f}₽\n"
        f"└─ Месяц: {revenue_month:.2f}₽\n\n"
        f"👥 <b>Активные:</b>\n"
        f"├─ День: {active_day}\n"
        f"├─ Неделя: {active_week}\n"
        f"└─ Месяц: {active_month}\n\n"
        f"🧾 <b>Средний чек:</b>\n"
        f"├─ День: {avg_day:.2f}₽\n"
        f"├─ Неделя: {avg_week:.2f}₽\n"
        f"└─ Месяц: {avg_month:.2f}₽\n\n"
        f"🏆 <b>Топ-5 покупателей:</b>\n"
    )
    for i, (username, fullname, total) in enumerate(top, 1):
        text += f"{i}. @{username or 'Аноним'} — {total:.2f}₽\n"
    await message.answer(text)

@router.message(Command("tickets"))
async def cmd_tickets(message: types.Message):
    if not has_access(message.from_user.id, 'moder'):
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
    text = f"📋 {title}:\n\n"
    for ticket in tickets[:20]:
        t_id, user_id, subject, status, _, _, priority, created_at = ticket[:8]
        user = get_user(user_id)
        username = user[2] if user else "Неизвестно"
        text += f"{priority} #{t_id} - @{username} - {subject} - {status} - {format_datetime(created_at)}\n\n"
    await message.answer(text)

@router.message(Command("ticket"))
async def cmd_ticket(message: types.Message):
    if not has_access(message.from_user.id, 'moder'):
        await message.answer("⛔ Нет доступа")
        return
    args = message.text.split()
    if len(args) < 2:
        await message.answer("❌ Использование: /ticket ID")
        return
    try:
        ticket_id = int(args[1])
    except ValueError:
        await message.answer("❌ ID должен быть числом")
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

@router.message(Command("answer"))
async def cmd_answer(message: types.Message):
    if not has_access(message.from_user.id, 'agent'):
        await message.answer("⛔ Нет доступа")
        return
    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        await message.answer("❌ Использование: /answer ID текст")
        return
    try:
        ticket_id = int(args[1])
    except ValueError:
        await message.answer("❌ ID должен быть числом")
        return
    answer_text = args[2]
    ticket = get_ticket(ticket_id)
    if not ticket:
        await message.answer("❌ Тикет не найден")
        return
    if ticket[3] == 'closed':
        await message.answer("❌ Тикет закрыт. Нельзя отправить ответ.")
        return
    add_ticket_message(ticket_id, message.from_user.id, answer_text, is_from_support=True)
    from main import bot
    try:
        await bot.send_message(
            ticket[1],
            f"📩 <b>Ответ на ваш тикет #{ticket_id}</b>\n\n{answer_text}"
        )
        await message.answer(f"✅ Ответ отправлен в тикет #{ticket_id}")
    except Exception as e:
        logger.error(f"Ошибка отправки ответа: {e}")
        await message.answer("❌ Не удалось отправить ответ пользователю")

@router.message(Command("creport"))
async def cmd_creport(message: types.Message):
    if not has_access(message.from_user.id, 'agent'):
        await message.answer("⛔ Нет доступа")
        return
    args = message.text.split()
    if len(args) < 2:
        await message.answer("❌ Использование: /creport ID")
        return
    try:
        ticket_id = int(args[1])
    except ValueError:
        await message.answer("❌ ID должен быть числом")
        return
    ticket = get_ticket(ticket_id)
    if not ticket:
        await message.answer("❌ Тикет не найден")
        return
    if ticket[3] == 'closed':
        await message.answer("❌ Тикет уже закрыт.")
        return
    update_ticket_status(ticket_id, 'closed')
    await message.answer(f"✅ Тикет #{ticket_id} закрыт")

# ========== ЗАГЛУШКА ==========
@router.callback_query(F.data == "no_action")
async def no_action(callback: types.CallbackQuery):
    await callback.answer("Это действие уже обработано", show_alert=True)