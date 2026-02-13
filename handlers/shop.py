# FILE: handlers/shop.py
import logging
import os
import uuid
from datetime import datetime, timedelta
from aiogram import Router, types, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import (
    STAR_RATE, MIN_STARS, SCREENSHOTS_DIR, OWNER_ID,
    REAL_TO_VIRTUAL_RATE, REAL_TO_VIRTUAL_MIN,
    VIRTUAL_TO_REAL_RATE, WITHDRAW_MIN_REAL,
    WITHDRAW_COMMISSION, EXCHANGE_COMMISSION, VIRTUAL_TO_REAL_COMMISSION
)
from database import (
    get_user, update_balance, create_order, get_order_status, update_order_status,
    get_promocode, use_promocode, check_promocode_valid, get_user_orders,
    create_withdrawal, get_pending_withdrawals, update_withdrawal_status,
    create_exchange, get_user_active_discount, mark_discount_used,
    create_feedback, get_order_feedback, update_feedback_status,
    create_discount_link, use_discount_link,
    get_db_connection, log_admin_action, cancel_order, add_order_comment
)
from keyboards import (
    MenuCallback, OrderCallback, WithdrawalCallback, ExchangeCallback,
    FeedbackCallback, get_main_menu,
    get_back_to_menu_keyboard, get_skip_promocode_keyboard,
    get_order_action_keyboard, get_processed_order_keyboard,
    get_withdrawal_keyboard,
    get_feedback_order_keyboard, get_calculator_menu,
    get_exchange_menu, get_cancel_reasons_keyboard,
    get_skip_keyboard, get_rating_keyboard
)
from states import PurchaseStates, ExchangeStates, WithdrawalStates, CalculatorStates
from utils import (
    get_screenshot_path, format_datetime, has_access,
    invalidate_balance_cache, invalidate_top_cache, is_duplicate_action
)

logger = logging.getLogger(__name__)

router = Router(name="shop")

# ========== РУЧНАЯ ПОКУПКА (ЧЕРЕЗ СКРИНШОТ) ==========
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
    if message.document.mime_type and message.document.mime_type.startswith('image/'):
        await _process_screenshot_file(message, state)
    else:
        await message.answer(
            "❌ Пожалуйста, отправьте скриншот в виде изображения (JPG, PNG и т.д.)",
            reply_markup=get_back_to_menu_keyboard()
        )

async def _process_screenshot_file(message: types.Message, state: FSMContext):
    from main import bot
    data = await state.get_data()
    user_id = message.from_user.id

    file_id = None
    if message.photo:
        file_id = message.photo[-1].file_id
    elif message.document:
        file_id = message.document.file_id

    if not file_id:
        await message.answer("❌ Не удалось получить изображение", reply_markup=get_back_to_menu_keyboard())
        return

    file_info = await bot.get_file(file_id)
    file_path = get_screenshot_path(user_id, f"{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg")
    await bot.download_file(file_info.file_path, file_path)

    final_price = data.get('final_price', data['total_price'])
    order_id = create_order(
        user_id=user_id,
        amount=data['amount'],
        recipient_username=data['recipient_username'],
        screenshot_path=file_path
    )

    if 'promocode' in data:
        promocode = get_promocode(data['promocode'])
        if promocode:
            use_promocode(user_id, promocode[0], order_id)
    else:
        discount = get_user_active_discount(user_id)
        if discount:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE orders SET discount = total_price * ? / 100 WHERE id = ?",
                (discount, order_id)
            )
            conn.commit()
            conn.close()
            mark_discount_used(user_id, order_id)

    order_text = (
        f"🆕 <b>Новая заявка #{order_id}</b>\n\n"
        f"👤 Покупатель: @{message.from_user.username or 'без юзернейма'}\n"
        f"⭐ Количество: {data['amount']} звёзд\n"
        f"💳 Сумма: {final_price:.2f}₽"
    )
    if 'promocode' in data:
        order_text += f"\n🎁 Промокод: {data['promocode']} (-{data['discount_percent']}%)"
    order_text += f"\n🎯 Получатель: {data['recipient_username']}"

    try:
        await bot.send_message(OWNER_ID, order_text)
        photo = FSInputFile(file_path)
        await bot.send_photo(OWNER_ID, photo, caption=f"Заявка #{order_id}",
                            reply_markup=get_order_action_keyboard(order_id))
    except Exception as e:
        logger.error(f"Ошибка отправки владельцу: {e}")

    await message.answer(
        "✅ Ваша заявка отправлена на проверку администратору!\nОжидайте подтверждения.",
        reply_markup=get_back_to_menu_keyboard()
    )
    await state.clear()

# ========== ПОДТВЕРЖДЕНИЕ/ОТКЛОНЕНИЕ ЗАКАЗОВ ==========
@router.callback_query(OrderCallback.filter(F.action == "approve"))
async def approve_order(callback: types.CallbackQuery, callback_data: OrderCallback):
    order_id = callback_data.order_id
    if not has_access(callback.from_user.id, 'admin'):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    current_status = get_order_status(order_id)
    if current_status != 'pending':
        await callback.answer(f"Этот заказ уже обработан ({current_status})", show_alert=True)
        return
    update_order_status(order_id, "approved")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT user_id, amount, recipient_username, total_price, discount FROM orders WHERE id = ?",
        (order_id,)
    )
    order = cursor.fetchone()
    conn.close()
    if order:
        user_id, amount, recipient_username, total_price, discount = order
        final_price = total_price - (discount or 0)
        try:
            from main import bot
            await bot.send_message(
                user_id,
                f"✅ <b>Заказ #{order_id} подтверждён!</b>\n\n"
                f"Количество: {amount} ⭐\n"
                f"Получатель: {recipient_username}\n"
                f"Сумма: {final_price:.2f}₽\n\n"
                f"Звёзды будут отправлены в ближайшее время."
            )
        except Exception as e:
            logger.error(f"Ошибка уведомления пользователя: {e}")
        log_admin_action(callback.from_user.id, 'approve_order', 'order', order_id, {'amount': amount})
        await invalidate_top_cache()

    await callback.message.edit_reply_markup(reply_markup=get_processed_order_keyboard("approved"))
    await callback.answer("✅ Заказ подтверждён", show_alert=True)

@router.callback_query(OrderCallback.filter(F.action == "reject"))
async def reject_order(callback: types.CallbackQuery, callback_data: OrderCallback):
    order_id = callback_data.order_id
    if not has_access(callback.from_user.id, 'admin'):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    current_status = get_order_status(order_id)
    if current_status != 'pending':
        await callback.answer(f"Этот заказ уже обработан ({current_status})", show_alert=True)
        return
    update_order_status(order_id, "rejected")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM orders WHERE id = ?", (order_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        user_id = row[0]
        try:
            from main import bot
            await bot.send_message(user_id, f"❌ Заявка #{order_id} отклонена. Обратитесь в поддержку.")
        except Exception as e:
            logger.error(f"Ошибка уведомления: {e}")
    await callback.message.edit_reply_markup(reply_markup=get_processed_order_keyboard("rejected"))
    await callback.answer("❌ Заказ отклонён", show_alert=True)

# ========== ОТМЕНА ЗАКАЗА ПОЛЬЗОВАТЕЛЕМ ==========
@router.callback_query(OrderCallback.filter(F.action == "cancel"))
async def cancel_order_callback(callback: types.CallbackQuery, callback_data: OrderCallback, state: FSMContext):
    order_id = callback_data.order_id
    user_id = callback.from_user.id
    orders = get_user_orders(user_id)
    if not any(o[0] == order_id for o in orders):
        await callback.answer("❌ Заказ не найден или вам не принадлежит", show_alert=True)
        return
    await state.update_data(cancel_order_id=order_id)
    await callback.message.edit_text(
        "🗑 <b>Отмена заказа</b>\n\n"
        "Выберите причину отмены:",
        reply_markup=get_cancel_reasons_keyboard(order_id)
    )
    await callback.answer()

@router.callback_query(F.data.startswith("cancel_reason_"))
async def cancel_reason_chosen(callback: types.CallbackQuery, state: FSMContext):
    reason_key = callback.data.replace("cancel_reason_", "")
    data = await state.get_data()
    order_id = data.get('cancel_order_id')
    if not order_id:
        await callback.answer("❌ Ошибка: заказ не найден", show_alert=True)
        return
    if reason_key == "custom":
        await callback.message.edit_text(
            "📝 Напишите свою причину отмены:",
            reply_markup=get_back_to_menu_keyboard()
        )
        await state.set_state(PurchaseStates.waiting_cancel_reason)
    else:
        reasons = {
            "wrong_amount": "Выбрал не правильную сумму",
            "wrong_recipient": "Неправильные данные получателя",
            "changed_mind": "Передумал",
            "other": "Другая причина"
        }
        reason_text = reasons.get(reason_key, "Не указана")
        if cancel_order(order_id, callback.from_user.id, reason_text):
            await callback.message.edit_text(
                f"✅ Заказ #{order_id} успешно отменён.\n"
                f"Причина: {reason_text}",
                reply_markup=get_back_to_menu_keyboard()
            )
        else:
            await callback.message.edit_text(
                "❌ Не удалось отменить заказ. Возможно, он уже обработан.",
                reply_markup=get_back_to_menu_keyboard()
            )
        await state.clear()
    await callback.answer()

@router.message(PurchaseStates.waiting_cancel_reason)
async def process_custom_cancel_reason(message: types.Message, state: FSMContext):
    data = await state.get_data()
    order_id = data.get('cancel_order_id')
    if not order_id:
        await message.answer("❌ Ошибка: заказ не найден", reply_markup=get_back_to_menu_keyboard())
        await state.clear()
        return
    reason_text = message.text.strip()
    if cancel_order(order_id, message.from_user.id, reason_text):
        await message.answer(
            f"✅ Заказ #{order_id} успешно отменён.\n"
            f"Причина: {reason_text}",
            reply_markup=get_back_to_menu_keyboard()
        )
    else:
        await message.answer(
            "❌ Не удалось отменить заказ. Возможно, он уже обработан.",
            reply_markup=get_back_to_menu_keyboard()
        )
    await state.clear()

# ========== КОММЕНТАРИЙ К ЗАКАЗУ ==========
@router.callback_query(OrderCallback.filter(F.action == "comment"))
async def add_comment_callback(callback: types.CallbackQuery, callback_data: OrderCallback, state: FSMContext):
    order_id = callback_data.order_id
    await state.update_data(comment_order_id=order_id)
    await callback.message.edit_text(
        "💬 <b>Добавить комментарий к заказу</b>\n\n"
        f"Заказ #{order_id}\n"
        "Введите текст комментария:",
        reply_markup=get_back_to_menu_keyboard()
    )
    await state.set_state(PurchaseStates.waiting_comment)
    await callback.answer()

@router.message(PurchaseStates.waiting_comment)
async def process_order_comment(message: types.Message, state: FSMContext):
    data = await state.get_data()
    order_id = data.get('comment_order_id')
    if not order_id:
        await message.answer("❌ Ошибка: заказ не найден", reply_markup=get_back_to_menu_keyboard())
        await state.clear()
        return
    comment = message.text.strip()
    if add_order_comment(order_id, message.from_user.id, comment):
        await message.answer(
            f"✅ Комментарий к заказу #{order_id} добавлен:\n\n{comment}",
            reply_markup=get_back_to_menu_keyboard()
        )
    else:
        await message.answer(
            "❌ Не удалось добавить комментарий. Заказ не найден или не принадлежит вам.",
            reply_markup=get_back_to_menu_keyboard()
        )
    await state.clear()

# ========== ОБМЕН ВАЛЮТ ==========
@router.callback_query(MenuCallback.filter(F.action == "exchange"))
async def show_exchange_menu(callback: types.CallbackQuery):
    text = (
        "💱 <b>Обмен валют</b>\n\n"
        f"<b>Курсы обмена:</b>\n"
        f"• Реальные → Виртуальные: 1:{REAL_TO_VIRTUAL_RATE}, минимум {REAL_TO_VIRTUAL_MIN} реальных звёзд\n"
        f"• Виртуальные → Реальные: 1:{VIRTUAL_TO_REAL_RATE}, комиссия {VIRTUAL_TO_REAL_COMMISSION*100}%\n\n"
        "Выберите направление:"
    )
    await callback.message.edit_text(text, reply_markup=get_exchange_menu())
    await callback.answer()

@router.callback_query(ExchangeCallback.filter(F.action == "start"))
async def start_exchange(callback: types.CallbackQuery, callback_data: ExchangeCallback, state: FSMContext):
    exchange_type = callback_data.exchange_type
    await state.update_data(exchange_type=exchange_type)

    if exchange_type == 'real_to_virtual':
        text = (
            f"💱 <b>Обмен реальных звёзд на виртуальные</b>\n\n"
            f"Курс: 1 реальная = {REAL_TO_VIRTUAL_RATE} виртуальных\n"
            f"Минимум: {REAL_TO_VIRTUAL_MIN} реальных звёзд\n\n"
            f"Введите количество реальных звёзд для обмена:"
        )
    else:
        min_virtual = int(WITHDRAW_MIN_REAL / (VIRTUAL_TO_REAL_RATE * (1 - VIRTUAL_TO_REAL_COMMISSION)))
        text = (
            f"💱 <b>Обмен виртуальных звёзд на реальные</b>\n\n"
            f"Курс: 1 виртуальная = {VIRTUAL_TO_REAL_RATE} реальных\n"
            f"Комиссия: {VIRTUAL_TO_REAL_COMMISSION*100}%\n"
            f"Минимум: {min_virtual} виртуальных звёзд ({WITHDRAW_MIN_REAL} реальных)\n\n"
            f"Введите количество виртуальных звёзд для обмена:"
        )
    await callback.message.edit_text(text, reply_markup=get_back_to_menu_keyboard())
    await state.set_state(ExchangeStates.waiting_for_exchange_amount)
    await callback.answer()

@router.message(ExchangeStates.waiting_for_exchange_amount)
async def process_exchange_amount(message: types.Message, state: FSMContext):
    try:
        amount = int(message.text)
        data = await state.get_data()
        exchange_type = data['exchange_type']
        user = get_user(message.from_user.id)

        if exchange_type == 'real_to_virtual':
            if amount < REAL_TO_VIRTUAL_MIN:
                await message.answer(f"❌ Минимальная сумма: {REAL_TO_VIRTUAL_MIN} реальных звёзд!")
                return
            if user[4] < amount:
                await message.answer("❌ Недостаточно реальных звёзд!")
                return

            exchange_id, converted, commission = create_exchange(
                message.from_user.id, 'real', 'virtual', amount
            )
            if exchange_id:
                if update_balance(message.from_user.id, amount, 'real', 'subtract'):
                    update_balance(message.from_user.id, converted, 'virtual', 'add')
                    await message.answer(
                        f"✅ Обмен выполнен!\n\n"
                        f"Обменено: {amount} реальных ⭐\n"
                        f"Получено: {converted} виртуальных ⭐\n"
                        f"Комиссия: {commission} виртуальных ⭐"
                    )
                else:
                    await message.answer("❌ Ошибка списания!")
            else:
                await message.answer("❌ Ошибка при обмене!")
            await state.clear()

        else:
            min_virtual = int(WITHDRAW_MIN_REAL / (VIRTUAL_TO_REAL_RATE * (1 - VIRTUAL_TO_REAL_COMMISSION)))
            if amount < min_virtual:
                await message.answer(f"❌ Минимум для обмена: {min_virtual} виртуальных звёзд!")
                return
            if user[5] < amount:
                await message.answer("❌ Недостаточно виртуальных звёзд!")
                return
            real_amount = int(amount * VIRTUAL_TO_REAL_RATE * (1 - VIRTUAL_TO_REAL_COMMISSION))
            await state.update_data(amount=amount, real_amount=real_amount)
            await message.answer(
                f"💱 <b>Детали обмена</b>\n\n"
                f"Обмениваем: {amount} виртуальных ⭐\n"
                f"Получите: {real_amount} реальных ⭐\n\n"
                f"Введите юзернейм получателя (куда отправить реальные звёзды):",
                reply_markup=get_back_to_menu_keyboard()
            )
            await state.set_state(ExchangeStates.waiting_for_recipient)
    except ValueError:
        await message.answer("❌ Введите число!")

@router.message(ExchangeStates.waiting_for_recipient)
async def process_exchange_recipient(message: types.Message, state: FSMContext):
    from main import bot
    recipient = message.text.strip()
    if not recipient.startswith('@'):
        recipient = '@' + recipient
    data = await state.get_data()
    user_id = message.from_user.id
    amount = data['amount']
    real_amount = data['real_amount']

    if not update_balance(user_id, amount, 'virtual', 'subtract'):
        await message.answer("❌ Ошибка списания!")
        await state.clear()
        return

    exchange_id, converted, commission = create_exchange(
        user_id=user_id,
        from_currency='virtual',
        to_currency='real',
        amount=amount,
        recipient_username=recipient
    )

    if not exchange_id:
        update_balance(user_id, amount, 'virtual', 'add')
        await message.answer("❌ Ошибка создания заявки!")
        await state.clear()
        return

    user = get_user(user_id)
    username = user[2] or "без юзернейма"

    exchange_text = (
        f"💱 <b>Новая заявка на обмен</b>\n\n"
        f"👤 Пользователь: @{username} (ID: {user_id})\n"
        f"📱 Получатель: {recipient}\n"
        f"⭐ Обменено: {amount} виртуальных\n"
        f"💰 Получит: {real_amount} реальных\n"
        f"💸 Комиссия: {commission} виртуальных\n"
        f"📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    )
    try:
        await bot.send_message(OWNER_ID, exchange_text)
    except Exception as e:
        logger.error(f"Ошибка отправки владельцу: {e}")

    await message.answer(
        f"✅ Заявка на обмен отправлена!\n\n"
        f"Обменено: {amount} виртуальных ⭐\n"
        f"Будет отправлено: {real_amount} реальных ⭐\n"
        f"Получатель: {recipient}",
        reply_markup=get_back_to_menu_keyboard()
    )
    await state.clear()

# ========== ОДОБРЕНИЕ/ОТКЛОНЕНИЕ ЗАЯВОК НА ОБМЕН (ДЛЯ АДМИНОВ) ==========
@router.callback_query(ExchangeCallback.filter(F.action == "approve"))
async def approve_exchange(callback: types.CallbackQuery, callback_data: ExchangeCallback):
    """Одобрение заявки на обмен виртуальных звёзд на реальные."""
    exchange_id = callback_data.exchange_id
    if not has_access(callback.from_user.id, 'admin'):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT user_id, converted_amount, recipient_username FROM exchanges WHERE exchange_id = ?",
        (exchange_id,)
    )
    result = cursor.fetchone()
    if result:
        user_id, converted_amount, recipient = result
        cursor.execute(
            "UPDATE exchanges SET status = 'approved' WHERE exchange_id = ?",
            (exchange_id,)
        )
        conn.commit()
        try:
            from main import bot
            await bot.send_message(
                user_id,
                f"✅ Ваша заявка на обмен #{exchange_id} одобрена!\n"
                f"Сумма к выдаче: {converted_amount} реальных ⭐\n"
                f"Получатель: {recipient}\n\n"
                f"Звёзды будут отправлены в ближайшее время."
            )
        except Exception as e:
            logger.error(f"Ошибка уведомления пользователя {user_id}: {e}")
        log_admin_action(callback.from_user.id, 'approve_exchange', 'exchange', None, {'exchange_id': exchange_id})
    conn.close()

    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer("✅ Заявка на обмен одобрена!", show_alert=True)

@router.callback_query(ExchangeCallback.filter(F.action == "reject"))
async def reject_exchange(callback: types.CallbackQuery, callback_data: ExchangeCallback):
    """Отклонение заявки на обмен виртуальных звёзд на реальные."""
    exchange_id = callback_data.exchange_id
    if not has_access(callback.from_user.id, 'admin'):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT user_id, amount FROM exchanges WHERE exchange_id = ?",
        (exchange_id,)
    )
    result = cursor.fetchone()
    if result:
        user_id, amount = result
        # Возвращаем виртуальные звёзды пользователю
        update_balance(user_id, amount, 'virtual', 'add')
        cursor.execute(
            "UPDATE exchanges SET status = 'rejected' WHERE exchange_id = ?",
            (exchange_id,)
        )
        conn.commit()
        try:
            from main import bot
            await bot.send_message(
                user_id,
                f"❌ Ваша заявка на обмен #{exchange_id} отклонена.\n"
                f"Сумма {amount} ⭐ возвращена на ваш виртуальный баланс."
            )
        except Exception as e:
            logger.error(f"Ошибка уведомления пользователя {user_id}: {e}")
        log_admin_action(callback.from_user.id, 'reject_exchange', 'exchange', None, {'exchange_id': exchange_id})
    conn.close()

    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer("❌ Заявка на обмен отклонена!", show_alert=True)

# ========== ВЫВОД ==========
@router.callback_query(MenuCallback.filter(F.action == "withdraw"))
async def start_withdrawal(callback: types.CallbackQuery, state: FSMContext):
    min_virtual = int(WITHDRAW_MIN_REAL / (VIRTUAL_TO_REAL_RATE * (1 - VIRTUAL_TO_REAL_COMMISSION)))
    text = (
        "📤 <b>Вывод виртуальных звёзд в реальные</b>\n\n"
        f"<b>Условия вывода:</b>\n"
        f"• Минимум: {min_virtual} виртуальных звёзд ({WITHDRAW_MIN_REAL} реальных)\n"
        f"• Комиссия: {WITHDRAW_COMMISSION*100}%\n\n"
        f"Введите количество виртуальных звёзд для вывода:"
    )
    await callback.message.edit_text(text, reply_markup=get_back_to_menu_keyboard())
    await state.set_state(WithdrawalStates.waiting_for_withdrawal_amount)
    await callback.answer()

@router.message(WithdrawalStates.waiting_for_withdrawal_amount)
async def process_withdrawal_amount(message: types.Message, state: FSMContext):
    try:
        amount = int(message.text)
        min_virtual = int(WITHDRAW_MIN_REAL / (VIRTUAL_TO_REAL_RATE * (1 - VIRTUAL_TO_REAL_COMMISSION)))
        if amount < min_virtual:
            await message.answer(f"❌ Минимум для вывода: {min_virtual} виртуальных звёзд!")
            return
        user = get_user(message.from_user.id)
        if user[5] < amount:
            await message.answer("❌ Недостаточно виртуальных звёзд!")
            return
        real_amount = int(amount * VIRTUAL_TO_REAL_RATE * (1 - WITHDRAW_COMMISSION))
        await state.update_data(amount=amount, real_amount=real_amount)
        await message.answer(
            f"📤 <b>Детали вывода</b>\n\n"
            f"Выводите: {amount} виртуальных ⭐\n"
            f"Получите: {real_amount} реальных ⭐ (комиссия {WITHDRAW_COMMISSION*100}%)\n\n"
            f"Введите юзернейм получателя:",
            reply_markup=get_back_to_menu_keyboard()
        )
        await state.set_state(WithdrawalStates.waiting_for_recipient)
    except ValueError:
        await message.answer("❌ Введите число!")

@router.message(WithdrawalStates.waiting_for_recipient)
async def process_withdrawal_recipient(message: types.Message, state: FSMContext):
    from main import bot
    recipient = message.text.strip()
    if not recipient.startswith('@'):
        recipient = '@' + recipient
    data = await state.get_data()
    user_id = message.from_user.id
    amount = data['amount']
    real_amount = data['real_amount']

    if not update_balance(user_id, amount, 'virtual', 'subtract'):
        await message.answer("❌ Ошибка списания!")
        await state.clear()
        return

    withdrawal_id = str(uuid.uuid4())
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """INSERT INTO withdrawals (withdrawal_id, user_id, amount, payout_amount, recipient_username, status) 
            VALUES (?, ?, ?, ?, ?, 'pending')""",
            (withdrawal_id, user_id, amount, real_amount, recipient)
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Ошибка создания заявки: {e}")
        update_balance(user_id, amount, 'virtual', 'add')
        await message.answer("❌ Ошибка создания заявки!")
        await state.clear()
        return
    finally:
        conn.close()

    user = get_user(user_id)
    username = user[2] or "без юзернейма"

    withdrawal_text = (
        f"📤 <b>Новая заявка на вывод #{withdrawal_id}</b>\n\n"
        f"👤 Пользователь: @{username} (ID: {user_id})\n"
        f"📱 Получатель: {recipient}\n"
        f"⭐ Выведено: {amount} виртуальных\n"
        f"💰 Получит: {real_amount} реальных"
    )
    try:
        await bot.send_message(OWNER_ID, withdrawal_text,
                              reply_markup=get_withdrawal_keyboard(withdrawal_id))
    except Exception as e:
        logger.error(f"Ошибка отправки владельцу: {e}")

    await message.answer(
        f"✅ Заявка на вывод отправлена!\n\n"
        f"Выведено: {amount} виртуальных ⭐\n"
        f"Будет отправлено: {real_amount} реальных ⭐\n"
        f"Получатель: {recipient}",
        reply_markup=get_back_to_menu_keyboard()
    )
    await state.clear()

@router.callback_query(WithdrawalCallback.filter(F.action == "approve"))
async def approve_withdrawal(callback: types.CallbackQuery, callback_data: WithdrawalCallback):
    withdrawal_id = callback_data.withdrawal_id
    if not has_access(callback.from_user.id, 'admin'):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    update_withdrawal_status(withdrawal_id, 'approved')
    await callback.answer("✅ Вывод одобрен!", show_alert=True)
    await callback.message.edit_reply_markup(reply_markup=None)

@router.callback_query(WithdrawalCallback.filter(F.action == "reject"))
async def reject_withdrawal(callback: types.CallbackQuery, callback_data: WithdrawalCallback):
    withdrawal_id = callback_data.withdrawal_id
    if not has_access(callback.from_user.id, 'admin'):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, amount FROM withdrawals WHERE withdrawal_id = ?", (withdrawal_id,))
    row = cursor.fetchone()
    if row:
        user_id, amount = row
        update_balance(user_id, amount, 'virtual', 'add')
    conn.close()
    update_withdrawal_status(withdrawal_id, 'rejected')
    await callback.answer("❌ Вывод отклонён!", show_alert=True)
    await callback.message.edit_reply_markup(reply_markup=None)

# ========== КАЛЬКУЛЯТОР ==========
@router.callback_query(MenuCallback.filter(F.action == "calculator"))
async def show_calculator(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "🧮 <b>Калькулятор</b>\n\nВыберите направление конвертации:",
        reply_markup=get_calculator_menu()
    )
    await callback.answer()

@router.callback_query(MenuCallback.filter(F.action == "calc_stars_to_rub"))
async def stars_to_rubles(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "Введите количество звёзд для конвертации в рубли:",
        reply_markup=get_back_to_menu_keyboard()
    )
    await state.set_state(CalculatorStates.waiting_for_stars)
    await callback.answer()

@router.message(CalculatorStates.waiting_for_stars)
async def process_calc_stars(message: types.Message, state: FSMContext):
    try:
        stars = int(message.text)
        rubles = stars * STAR_RATE
        await message.answer(
            f"⭐ {stars} звёзд = 💰 {rubles:.2f}₽",
            reply_markup=get_back_to_menu_keyboard()
        )
        await state.clear()
    except ValueError:
        await message.answer("❌ Введите число!")

@router.callback_query(MenuCallback.filter(F.action == "calc_rub_to_stars"))
async def rubles_to_stars(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "Введите сумму в рублях для конвертации в звёзды:",
        reply_markup=get_back_to_menu_keyboard()
    )
    await state.set_state(CalculatorStates.waiting_for_rubles)
    await callback.answer()

@router.message(CalculatorStates.waiting_for_rubles)
async def process_calc_rubles(message: types.Message, state: FSMContext):
    try:
        rubles = float(message.text)
        stars = rubles / STAR_RATE
        await message.answer(
            f"💰 {rubles:.2f}₽ = ⭐ {stars:.1f} звёзд",
            reply_markup=get_back_to_menu_keyboard()
        )
        await state.clear()
    except ValueError:
        await message.answer("❌ Введите число!")

# ========== ССЫЛКИ СО СКИДКОЙ (ОБРАБОТКА СТАРТА) ==========
@router.message(CommandStart(deep_link=True, magic=F.args.startswith("discount_")))
async def process_discount_start(message: types.Message):
    args = message.text.split()[1] if len(message.text.split()) > 1 else ""
    if not args.startswith("discount_"):
        return
    code = args.replace("discount_", "")
    user_id = message.from_user.id
    discount, msg = use_discount_link(code, user_id)
    if discount:
        await message.answer(
            f"🎁 <b>Ссылка активирована!</b>\n\n"
            f"Вы получили скидку <b>{discount}%</b> на следующую покупку!\n"
            f"Она будет применена автоматически при оформлении заказа.",
            reply_markup=get_main_menu()
        )
    else:
        await message.answer(
            f"❌ {msg}",
            reply_markup=get_main_menu()
        )

# ========== ОТЗЫВЫ ==========
@router.message(Command("feedback"))
async def cmd_feedback(message: types.Message):
    user_id = message.from_user.id
    orders = get_user_orders(user_id)
    approved_orders = [o for o in orders if o[3] == 'approved' and not get_order_feedback(o[0])]
    if not approved_orders:
        await message.answer("📭 Нет заказов, которые можно оценить.")
        return
    text = "📝 <b>ОСТАВИТЬ ОТЗЫВ</b>\n\nВыберите заказ из истории:\n\n"
    builder = InlineKeyboardBuilder()
    for order in approved_orders[:10]:
        order_id, amount, price, status, created_at, purchased = order
        date = format_datetime(purchased or created_at)
        text += f"✅ #{order_id} — {amount}⭐ — {price:.2f}₽ — {date}\n"
        builder.row(InlineKeyboardButton(text=f"#{order_id}", callback_data=FeedbackCallback(action="rate", order_id=order_id).pack()))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=MenuCallback(action="back_to_menu").pack()))
    await message.answer(text, reply_markup=builder.as_markup())

@router.callback_query(FeedbackCallback.filter(F.action == "rate"))
async def feedback_rate(callback: types.CallbackQuery, callback_data: FeedbackCallback, state: FSMContext):
    order_id = callback_data.order_id
    await state.update_data(order_id=order_id)
    await callback.message.edit_text(
        f"📝 <b>ОТЗЫВ О ЗАКАЗЕ #{order_id}</b>\n\nОцените покупку от 1 до 5:",
        reply_markup=get_feedback_order_keyboard(order_id)
    )
    await callback.answer()

@router.callback_query(FeedbackCallback.filter(F.action.startswith("rate_")))
async def feedback_submit(callback: types.CallbackQuery, callback_data: FeedbackCallback, state: FSMContext):
    rating = int(callback_data.action.split('_')[1])
    data = await state.get_data()
    order_id = data.get('order_id')
    if not order_id:
        await callback.answer("❌ Ошибка", show_alert=True)
        return
    user_id = callback.from_user.id
    feedback_id = create_feedback(user_id, order_id, rating)
    if feedback_id:
        await callback.message.edit_text(
            "✅ Спасибо за отзыв!\n\nЕсли хотите, можете оставить текстовый комментарий или фото:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📝 Написать комментарий", callback_data=FeedbackCallback(action="add_text", feedback_id=feedback_id).pack())],
                [InlineKeyboardButton(text="📸 Прикрепить фото", callback_data=FeedbackCallback(action="add_photo", feedback_id=feedback_id).pack())],
                [InlineKeyboardButton(text="⬅️ Завершить", callback_data=MenuCallback(action="back_to_menu").pack())]
            ])
        )
    else:
        await callback.message.edit_text("❌ Ошибка сохранения отзыва.", reply_markup=get_back_to_menu_keyboard())
    await state.clear()
    await callback.answer()

@router.callback_query(FeedbackCallback.filter(F.action == "add_text"))
async def feedback_add_text(callback: types.CallbackQuery, callback_data: FeedbackCallback, state: FSMContext):
    feedback_id = callback_data.feedback_id
    await state.update_data(feedback_id=feedback_id)
    await callback.message.edit_text(
        "📝 Введите текст отзыва:",
        reply_markup=get_back_to_menu_keyboard()
    )
    await state.set_state("waiting_feedback_text")
    await callback.answer()

@router.message(F.text)
async def process_feedback_text(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state != "waiting_feedback_text":
        return
    data = await state.get_data()
    feedback_id = data.get('feedback_id')
    if not feedback_id:
        await message.answer("❌ Ошибка")
        await state.clear()
        return
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE feedback SET text = ? WHERE id = ?", (message.text, feedback_id))
    conn.commit()
    conn.close()
    await message.answer("✅ Комментарий добавлен! Спасибо!")
    await state.clear()

@router.callback_query(FeedbackCallback.filter(F.action == "add_photo"))
async def feedback_add_photo(callback: types.CallbackQuery, callback_data: FeedbackCallback, state: FSMContext):
    feedback_id = callback_data.feedback_id
    await state.update_data(feedback_id=feedback_id)
    await callback.message.edit_text(
        "📸 Отправьте фото:",
        reply_markup=get_back_to_menu_keyboard()
    )
    await state.set_state("waiting_feedback_photo")
    await callback.answer()

@router.message(F.photo, lambda msg: msg.media_group_id is None)
async def process_feedback_photo(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state != "waiting_feedback_photo":
        return
    data = await state.get_data()
    feedback_id = data.get('feedback_id')
    if not feedback_id:
        await message.answer("❌ Ошибка")
        await state.clear()
        return
    photo = message.photo[-1]
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE feedback SET photo_id = ? WHERE id = ?", (photo.file_id, feedback_id))
    conn.commit()
    conn.close()
    await message.answer("✅ Фото добавлено! Спасибо!")
    await state.clear()

# ========== ЭКСПОРТ ХЭНДЛЕРОВ ==========
def register_handlers(dp):
    dp.include_router(router)