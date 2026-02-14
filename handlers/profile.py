# FILE: handlers/profile.py
import logging
from datetime import datetime
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import BOT_USERNAME
from database import (
    get_user, get_user_orders, get_warns, get_user_referrals, get_db_connection,
    get_user_achievements, get_all_achievements, get_referral_level, get_referral_levels,
    get_cached_top_buyers, invalidate_top_cache, is_user_frozen, get_freeze_info,
    create_user  # <-- ДОБАВЛЕНО для создания пользователя
)
from keyboards import MenuCallback, get_back_to_menu_keyboard, get_referrals_keyboard
from helpers import (  # <-- ИЗМЕНЕНО: вместо from utils
    format_datetime, get_role_display, generate_referral_code, has_access
)

logger = logging.getLogger(__name__)

router = Router(name="profile")

# ========== ПРОФИЛЬ ==========
@router.message(Command("profile"))
async def cmd_profile(message: types.Message):
    user_id = message.from_user.id
    await show_profile_internal(message, user_id, edit=False)

@router.callback_query(MenuCallback.filter(F.action == "profile"))
async def show_profile(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    await show_profile_internal(callback.message, user_id, edit=True)
    await callback.answer()

async def show_profile_internal(message: types.Message, user_id: int, edit: bool = False):
    user = get_user(user_id)
    if not user:
        # Пытаемся создать пользователя
        username = message.from_user.username or ""
        full_name = message.from_user.full_name or f"User {user_id}"
        create_user(user_id, username, full_name)
        user = get_user(user_id)
        if not user:
            await message.answer("❌ Не удалось создать профиль. Попробуйте позже.")
            return

    virtual_balance = user[5]
    total_spent = user[6]
    role = user[7] if len(user) > 7 else 'user'
    role_display = get_role_display(role)

    referrals = get_user_referrals(user_id)
    referrals_count = len(referrals)

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM referral_rewards WHERE referrer_id = ?",
        (user_id,)
    )
    referrals_earnings = cursor.fetchone()[0]
    conn.close()

    level = get_referral_level(referrals_count)

    frozen = is_user_frozen(user_id)
    freeze_info = get_freeze_info(user_id) if frozen else None

    profile_text = (
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"     👤 ПРОФИЛЬ     \n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🆔 ID: <code>{user[1]}</code>\n"
        f"👤 Имя: {user[3]}\n"
        f"🎖️ Статус: {role_display}\n"
    )

    if frozen:
        profile_text += (
            f"\n⚠️ СТАТУС: ❄️ ЗАМОРОЖЕН\n"
            f"🧊 Причина: {freeze_info[0] if freeze_info else 'Не указана'}\n"
            f"📅 Дата заморозки: {format_datetime(freeze_info[1]) if freeze_info else 'Неизвестно'}\n\n"
            f"🎮 Виртуальный баланс: {virtual_balance} ⭐ (❌ заморожен)\n"
        )
    else:
        profile_text += f"\n🎮 Виртуальный баланс: {virtual_balance} ⭐\n"

    profile_text += (
        f"📊 Всего потрачено: {total_spent:.2f}₽\n"
        f"👥 Рефералов: {referrals_count}\n"
        f"💎 Заработано с рефералов: {referrals_earnings} ⭐\n"
        f"📈 Уровень: {level['name']} ({level['percent']}%)\n\n"
    )

    if user[8]:
        profile_text += f"🔗 Ваш реферальный код: <code>ref_{user[8]}</code>\n"
        profile_text += f"🔗 Ваша реферальная ссылка: https://t.me/{BOT_USERNAME}?start={user[1]}\n\n"

    if frozen:
        profile_text += (
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"❗ Для разморозки обратитесь в поддержку\n"
            f"🆘 \n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🏆 Ачивки", callback_data=MenuCallback(action="achievements").pack()),
        InlineKeyboardButton(text="📜 История", callback_data=MenuCallback(action="purchase_history").pack()),
        width=2
    )
    builder.row(
        InlineKeyboardButton(text="👥 Мои рефералы", callback_data=MenuCallback(action="referrals").pack()),
    )
    builder.row(
        InlineKeyboardButton(text="⬅️ Назад", callback_data=MenuCallback(action="back_to_menu").pack()),
    )

    if edit:
        await message.edit_text(profile_text, reply_markup=builder.as_markup())
    else:
        await message.answer(profile_text, reply_markup=builder.as_markup())

# ========== АЧИВКИ ==========
@router.callback_query(MenuCallback.filter(F.action == "achievements"))
async def show_achievements(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    user_achs = get_user_achievements(user_id)
    all_achs = get_all_achievements()

    earned = {ach[0]: ach[4] for ach in user_achs}

    text = "━━━━━━━━━━━━━━━━━━━━\n   🏆 МОИ ДОСТИЖЕНИЯ   \n━━━━━━━━━━━━━━━━━━━━\n\n"
    count = 0
    for ach in all_achs:
        code, name, desc, icon, hidden, created = ach
        if hidden:
            continue
        if code in earned:
            text += f"✅ {icon} {name}\n   {desc}\n\n"
            count += 1
        else:
            text += f"⬜ {icon} {name}\n   {desc}\n"
            # Прогресс для некоторых ачивок
            user = get_user(user_id)
            if code == 'spent_50k':
                total = user[6] or 0
                progress = min(100, int(total / 50000 * 100))
                bar = "█" * (progress // 10) + "░" * (10 - progress // 10)
                text += f"   Прогресс: {bar} {total:.0f} / 50 000₽\n"
            elif code == 'games_100':
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM games WHERE user_id = ? AND game_type = 'casino_virtual'", (user_id,))
                games = cursor.fetchone()[0]
                conn.close()
                progress = min(100, int(games / 100 * 100))
                bar = "█" * (progress // 10) + "░" * (10 - progress // 10)
                text += f"   Прогресс: {bar} {games} / 100\n"
            elif code == 'veteran_1year':
                days = (datetime.now() - datetime.strptime(user[10], '%Y-%m-%d %H:%M:%S')).days if user[10] else 0
                progress = min(100, int(days / 365 * 100))
                bar = "█" * (progress // 10) + "░" * (10 - progress // 10)
                text += f"   Прогресс: {bar} {days} / 365 дней\n"
            elif code == 'referrer_10':
                refs = len(get_user_referrals(user_id))
                progress = min(100, int(refs / 10 * 100))
                bar = "█" * (progress // 10) + "░" * (10 - progress // 10)
                text += f"   Прогресс: {bar} {refs} / 10\n"
            text += "\n"

    text += f"━━━━━━━━━━━━━━━━━━━━\n📊 Всего ачивок: {count} / {len([a for a in all_achs if not a[4]])}\n━━━━━━━━━━━━━━━━━━━━"

    await callback.message.edit_text(text, reply_markup=get_back_to_menu_keyboard())
    await callback.answer()

# ========== РЕФЕРАЛЫ ==========
@router.callback_query(MenuCallback.filter(F.action == "referrals"))
async def show_referrals(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    user = get_user(user_id)
    referrals = get_user_referrals(user_id)
    referrals_count = len(referrals)
    level = get_referral_level(referrals_count)

    active = 0
    total_turnover = 0
    earned = 0
    conn = get_db_connection()
    cursor = conn.cursor()
    for ref in referrals:
        ref_id = ref[0]
        cursor.execute("SELECT SUM(total_price) FROM purchase_history WHERE user_id = ?", (ref_id,))
        turnover = cursor.fetchone()[0] or 0
        total_turnover += turnover
        if turnover > 0:
            active += 1
    cursor.execute("SELECT SUM(amount) FROM referral_rewards WHERE referrer_id = ? AND paid = 1", (user_id,))
    earned = cursor.fetchone()[0] or 0
    conn.close()

    text = (
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"   👥 МОИ РЕФЕРАЛЫ   \n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📊 УРОВЕНЬ: {level['min']}+ / {level['name']} ({level['percent']}%)\n"
        f"   Приглашено: {referrals_count}\n"
        f"   Активных: {active} ({active/referrals_count*100:.0f}%)\n"
        f"   Общий оборот: {total_turnover:.2f}₽\n"
        f"   Заработано: {earned:.0f} ⭐\n\n"
    )

    if referrals:
        text += "👤 АКТИВНЫЕ РЕФЕРАЛЫ:\n"
        shown = 0
        conn = get_db_connection()
        cursor = conn.cursor()
        for ref in referrals[:5]:
            ref_id, ref_username, ref_name, joined = ref
            cursor.execute("SELECT COUNT(*), SUM(total_price) FROM purchase_history WHERE user_id = ?", (ref_id,))
            purchases, spent = cursor.fetchone()
            purchases = purchases or 0
            spent = spent or 0
            if purchases > 0:
                shown += 1
                reward = spent * level['percent'] / 100
                text += f"━━━━━━━━━━━━━━━━━━━━\n"
                text += f"{shown}. @{ref_username or 'no_username'}\n"
                text += f"   ├─ Покупок: {purchases}\n"
                text += f"   ├─ Оборот: {spent:.2f}₽\n"
                text += f"   └─ Ваш доход: {reward:.0f} ⭐\n"
        conn.close()
        if len(referrals) > 5:
            text += f"\n... и ещё {len(referrals)-5} рефералов\n"
    else:
        text += "У вас пока нет рефералов.\n\n"

    next_level = None
    for lvl in get_referral_levels():
        if lvl['min'] > level['min']:
            next_level = lvl
            break
    if next_level:
        need = next_level['min'] - referrals_count
        potential = total_turnover * (next_level['percent'] - level['percent']) / 100
        text += (
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📈 ПРОГНОЗ:\n"
            f"   До следующего уровня ({next_level['name']}): +{need}\n"
            f"   Потенциальный доход: +{potential:.0f} ⭐\n"
        )

    text += f"\n🔗 ВАША РЕФЕРАЛЬНАЯ ССЫЛКА:\n"
    text += f"https://t.me/{BOT_USERNAME}?start={user_id}\n"
    if user[8]:
        text += f"Код: <code>ref_{user[8]}</code>"

    await callback.message.edit_text(
        text,
        reply_markup=get_referrals_keyboard()
    )
    await callback.answer()

# ========== ТОП ПОКУПАТЕЛЕЙ ==========
@router.callback_query(MenuCallback.filter(F.action == "top_buyers"))
async def show_top_buyers(callback: types.CallbackQuery):
    top = await get_cached_top_buyers(10)
    if not top:
        await callback.message.edit_text("🏆 Топ покупателей пока пуст.", reply_markup=get_back_to_menu_keyboard())
        await callback.answer()
        return

    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    text = "━━━━━━━━━━━━━━━━━━━━\n     🏆 ТОП-10     \n━━━━━━━━━━━━━━━━━━━━\n\n"
    for i, (username, fullname, total) in enumerate(top):
        medal = medals[i] if i < 3 else f"{i+1}."
        username_disp = f"@{username}" if username else "Аноним"
        text += f"{medal} {username_disp} — {total:.2f}₽\n"
    text += f"\n━━━━━━━━━━━━━━━━━━━━\n🔄 Обновляется каждые 10 мин"

    await callback.message.edit_text(text, reply_markup=get_back_to_menu_keyboard())
    await callback.answer()

# ========== ИСТОРИЯ ПОКУПОК ==========
@router.callback_query(MenuCallback.filter(F.action == "purchase_history"))
async def purchase_history(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    orders = get_user_orders(user_id)
    if not orders:
        await callback.message.edit_text("📭 У вас пока нет покупок.", reply_markup=get_back_to_menu_keyboard())
        await callback.answer()
        return
    text = "📜 <b>ИСТОРИЯ ПОКУПОК</b>\n\n"
    for order in orders[:15]:
        order_id, amount, final_price, status, created_at, purchase_date = order
        date = purchase_date or created_at
        status_icon = "✅" if status == 'approved' else "⏳" if status == 'pending' else "❌"
        text += f"{status_icon} #{order_id}: {amount}⭐ — {final_price:.2f}₽ — {format_datetime(date)}\n"
    text += "\n[📝 Оставить отзыв] - через /feedback"
    await callback.message.edit_text(text, reply_markup=get_back_to_menu_keyboard())
    await callback.answer()    if not user:
        await message.answer("❌ Профиль не найден.")
        return

    virtual_balance = user[5]
    total_spent = user[6]
    role = user[7] if len(user) > 7 else 'user'
    role_display = get_role_display(role)

    referrals = get_user_referrals(user_id)
    referrals_count = len(referrals)

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM referral_rewards WHERE referrer_id = ?",
        (user_id,)
    )
    referrals_earnings = cursor.fetchone()[0]
    conn.close()

    level = get_referral_level(referrals_count)

    frozen = is_user_frozen(user_id)
    freeze_info = get_freeze_info(user_id) if frozen else None

    profile_text = (
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"     👤 ПРОФИЛЬ     \n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🆔 ID: <code>{user[1]}</code>\n"
        f"👤 Имя: {user[3]}\n"
        f"🎖️ Статус: {role_display}\n"
    )

    if frozen:
        profile_text += (
            f"\n⚠️ СТАТУС: ❄️ ЗАМОРОЖЕН\n"
            f"🧊 Причина: {freeze_info[0] if freeze_info else 'Не указана'}\n"
            f"📅 Дата заморозки: {format_datetime(freeze_info[1]) if freeze_info else 'Неизвестно'}\n\n"
            f"🎮 Виртуальный баланс: {virtual_balance} ⭐ (❌ заморожен)\n"
        )
    else:
        profile_text += f"\n🎮 Виртуальный баланс: {virtual_balance} ⭐\n"

    profile_text += (
        f"📊 Всего потрачено: {total_spent:.2f}₽\n"
        f"👥 Рефералов: {referrals_count}\n"
        f"💎 Заработано с рефералов: {referrals_earnings} ⭐\n"
        f"📈 Уровень: {level['name']} ({level['percent']}%)\n\n"
    )

    if user[8]:
        profile_text += f"🔗 Ваш реферальный код: <code>ref_{user[8]}</code>\n"
        profile_text += f"🔗 Ваша реферальная ссылка: https://t.me/{BOT_USERNAME}?start={user[1]}\n\n"

    if frozen:
        profile_text += (
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"❗ Для разморозки обратитесь в поддержку\n"
            f"🆘 \n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🏆 Ачивки", callback_data=MenuCallback(action="achievements").pack()),
        InlineKeyboardButton(text="📜 История", callback_data=MenuCallback(action="purchase_history").pack()),
        width=2
    )
    builder.row(
        InlineKeyboardButton(text="👥 Мои рефералы", callback_data=MenuCallback(action="referrals").pack()),
    )
    builder.row(
        InlineKeyboardButton(text="⬅️ Назад", callback_data=MenuCallback(action="back_to_menu").pack()),
    )

    if edit:
        await message.edit_text(profile_text, reply_markup=builder.as_markup())
    else:
        await message.answer(profile_text, reply_markup=builder.as_markup())

# ========== АЧИВКИ ==========
@router.callback_query(MenuCallback.filter(F.action == "achievements"))
async def show_achievements(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    user_achs = get_user_achievements(user_id)
    all_achs = get_all_achievements()

    earned = {ach[0]: ach[4] for ach in user_achs}

    text = "━━━━━━━━━━━━━━━━━━━━\n   🏆 МОИ ДОСТИЖЕНИЯ   \n━━━━━━━━━━━━━━━━━━━━\n\n"
    count = 0
    for ach in all_achs:
        code, name, desc, icon, hidden, created = ach
        if hidden:
            continue
        if code in earned:
            text += f"✅ {icon} {name}\n   {desc}\n\n"
            count += 1
        else:
            text += f"⬜ {icon} {name}\n   {desc}\n"
            # Прогресс для некоторых ачивок
            user = get_user(user_id)
            if code == 'spent_50k':
                total = user[6] or 0
                progress = min(100, int(total / 50000 * 100))
                bar = "█" * (progress // 10) + "░" * (10 - progress // 10)
                text += f"   Прогресс: {bar} {total:.0f} / 50 000₽\n"
            elif code == 'games_100':
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM games WHERE user_id = ? AND game_type = 'casino_virtual'", (user_id,))
                games = cursor.fetchone()[0]
                conn.close()
                progress = min(100, int(games / 100 * 100))
                bar = "█" * (progress // 10) + "░" * (10 - progress // 10)
                text += f"   Прогресс: {bar} {games} / 100\n"
            elif code == 'veteran_1year':
                days = (datetime.now() - datetime.strptime(user[10], '%Y-%m-%d %H:%M:%S')).days if user[10] else 0
                progress = min(100, int(days / 365 * 100))
                bar = "█" * (progress // 10) + "░" * (10 - progress // 10)
                text += f"   Прогресс: {bar} {days} / 365 дней\n"
            elif code == 'referrer_10':
                refs = len(get_user_referrals(user_id))
                progress = min(100, int(refs / 10 * 100))
                bar = "█" * (progress // 10) + "░" * (10 - progress // 10)
                text += f"   Прогресс: {bar} {refs} / 10\n"
            text += "\n"

    text += f"━━━━━━━━━━━━━━━━━━━━\n📊 Всего ачивок: {count} / {len([a for a in all_achs if not a[4]])}\n━━━━━━━━━━━━━━━━━━━━"

    await callback.message.edit_text(text, reply_markup=get_back_to_menu_keyboard())
    await callback.answer()

# ========== РЕФЕРАЛЫ ==========
@router.callback_query(MenuCallback.filter(F.action == "referrals"))
async def show_referrals(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    user = get_user(user_id)
    referrals = get_user_referrals(user_id)
    referrals_count = len(referrals)
    level = get_referral_level(referrals_count)

    active = 0
    total_turnover = 0
    earned = 0
    conn = get_db_connection()
    cursor = conn.cursor()
    for ref in referrals:
        ref_id = ref[0]
        cursor.execute("SELECT SUM(total_price) FROM purchase_history WHERE user_id = ?", (ref_id,))
        turnover = cursor.fetchone()[0] or 0
        total_turnover += turnover
        if turnover > 0:
            active += 1
    cursor.execute("SELECT SUM(amount) FROM referral_rewards WHERE referrer_id = ? AND paid = 1", (user_id,))
    earned = cursor.fetchone()[0] or 0
    conn.close()

    text = (
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"   👥 МОИ РЕФЕРАЛЫ   \n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📊 УРОВЕНЬ: {level['min']}+ / {level['name']} ({level['percent']}%)\n"
        f"   Приглашено: {referrals_count}\n"
        f"   Активных: {active} ({active/referrals_count*100:.0f}%)\n"
        f"   Общий оборот: {total_turnover:.2f}₽\n"
        f"   Заработано: {earned:.0f} ⭐\n\n"
    )

    if referrals:
        text += "👤 АКТИВНЫЕ РЕФЕРАЛЫ:\n"
        shown = 0
        conn = get_db_connection()
        cursor = conn.cursor()
        for ref in referrals[:5]:
            ref_id, ref_username, ref_name, joined = ref
            cursor.execute("SELECT COUNT(*), SUM(total_price) FROM purchase_history WHERE user_id = ?", (ref_id,))
            purchases, spent = cursor.fetchone()
            purchases = purchases or 0
            spent = spent or 0
            if purchases > 0:
                shown += 1
                reward = spent * level['percent'] / 100
                text += f"━━━━━━━━━━━━━━━━━━━━\n"
                text += f"{shown}. @{ref_username or 'no_username'}\n"
                text += f"   ├─ Покупок: {purchases}\n"
                text += f"   ├─ Оборот: {spent:.2f}₽\n"
                text += f"   └─ Ваш доход: {reward:.0f} ⭐\n"
        conn.close()
        if len(referrals) > 5:
            text += f"\n... и ещё {len(referrals)-5} рефералов\n"
    else:
        text += "У вас пока нет рефералов.\n\n"

    next_level = None
    for lvl in get_referral_levels():
        if lvl['min'] > level['min']:
            next_level = lvl
            break
    if next_level:
        need = next_level['min'] - referrals_count
        potential = total_turnover * (next_level['percent'] - level['percent']) / 100
        text += (
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📈 ПРОГНОЗ:\n"
            f"   До следующего уровня ({next_level['name']}): +{need}\n"
            f"   Потенциальный доход: +{potential:.0f} ⭐\n"
        )

    text += f"\n🔗 ВАША РЕФЕРАЛЬНАЯ ССЫЛКА:\n"
    text += f"https://t.me/{BOT_USERNAME}?start={user_id}\n"
    if user[8]:
        text += f"Код: <code>ref_{user[8]}</code>"

    await callback.message.edit_text(
        text,
        reply_markup=get_referrals_keyboard()
    )
    await callback.answer()

# ========== ТОП ПОКУПАТЕЛЕЙ ==========
@router.callback_query(MenuCallback.filter(F.action == "top_buyers"))
async def show_top_buyers(callback: types.CallbackQuery):
    top = await get_cached_top_buyers(10)
    if not top:
        await callback.message.edit_text("🏆 Топ покупателей пока пуст.", reply_markup=get_back_to_menu_keyboard())
        await callback.answer()
        return

    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    text = "━━━━━━━━━━━━━━━━━━━━\n     🏆 ТОП-10     \n━━━━━━━━━━━━━━━━━━━━\n\n"
    for i, (username, fullname, total) in enumerate(top):
        medal = medals[i] if i < 3 else f"{i+1}."
        username_disp = f"@{username}" if username else "Аноним"
        text += f"{medal} {username_disp} — {total:.2f}₽\n"
    text += f"\n━━━━━━━━━━━━━━━━━━━━\n🔄 Обновляется каждые 10 мин"

    await callback.message.edit_text(text, reply_markup=get_back_to_menu_keyboard())
    await callback.answer()

# ========== ИСТОРИЯ ПОКУПОК ==========
@router.callback_query(MenuCallback.filter(F.action == "purchase_history"))
async def purchase_history(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    orders = get_user_orders(user_id)
    if not orders:
        await callback.message.edit_text("📭 У вас пока нет покупок.", reply_markup=get_back_to_menu_keyboard())
        await callback.answer()
        return
    text = "📜 <b>ИСТОРИЯ ПОКУПОК</b>\n\n"
    for order in orders[:15]:
        order_id, amount, final_price, status, created_at, purchase_date = order
        date = purchase_date or created_at
        status_icon = "✅" if status == 'approved' else "⏳" if status == 'pending' else "❌"
        text += f"{status_icon} #{order_id}: {amount}⭐ — {final_price:.2f}₽ — {format_datetime(date)}\n"
    text += "\n[📝 Оставить отзыв] - через /feedback"
    await callback.message.edit_text(text, reply_markup=get_back_to_menu_keyboard())
    await callback.answer()
