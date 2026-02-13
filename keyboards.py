# FILE: keyboards.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters.callback_data import CallbackData
from typing import Optional, List, Dict, Any
from config import CASINO_BET_AMOUNTS, STARS_PRICES, TICKET_SUBJECTS

# ========== БАЗОВЫЕ CALLBACKDATA ==========
class MenuCallback(CallbackData, prefix="menu"):
    action: str

class OrderCallback(CallbackData, prefix="order"):
    action: str
    order_id: int

class TicketCallback(CallbackData, prefix="ticket"):
    action: str
    ticket_id: int

class SubjectCallback(CallbackData, prefix="subject"):
    subject_id: int

class GameCallback(CallbackData, prefix="game"):
    action: str
    game_id: str = ""
    choice: int = 0
    bet_type: str = ""
    bet_amount: int = 0

class WithdrawalCallback(CallbackData, prefix="withdrawal"):
    action: str
    withdrawal_id: str

class ExchangeCallback(CallbackData, prefix="exchange"):
    action: str
    exchange_type: str = ""
    exchange_id: str = ""

class StarsPurchaseCallback(CallbackData, prefix="stars"):
    amount: int

# ========== НОВЫЕ CALLBACKDATA ДЛЯ АДМИНКИ И ФИЧ ==========
class AdminCallback(CallbackData, prefix="admin"):
    action: str
    page: int = 0
    target_id: int = 0
    data: str = ""

class PromocodeCallback(CallbackData, prefix="promo"):
    action: str
    promo_id: int = 0
    page: int = 0

class DiscountLinkCallback(CallbackData, prefix="discount"):
    action: str
    code: str = ""
    page: int = 0

# Алиас для обратной совместимости
DiscountCallback = DiscountLinkCallback

class UserCallback(CallbackData, prefix="user"):
    action: str
    user_id: int = 0
    page: int = 0
    data: str = ""

class AchievementCallback(CallbackData, prefix="ach"):
    action: str
    code: str = ""
    page: int = 0

class MailingCallback(CallbackData, prefix="mail"):
    action: str
    mailing_id: int = 0
    page: int = 0

class BackupCallback(CallbackData, prefix="backup"):
    action: str
    filename: str = ""
    page: int = 0

class SettingsCallback(CallbackData, prefix="set"):
    action: str
    key: str = ""
    page: int = 0

class FeedbackCallback(CallbackData, prefix="fb"):
    action: str
    order_id: int = 0
    feedback_id: int = 0

class TemplateCallback(CallbackData, prefix="template"):
    """Callback для работы с шаблонами тикетов (на случай использования)"""
    action: str
    template_id: int = 0
    name: str = ""
    page: int = 0

# ========== СУЩЕСТВУЮЩИЕ КЛАВИАТУРЫ (ОБНОВЛЁННЫЕ) ==========
def get_main_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="⭐ Профиль", callback_data=MenuCallback(action="profile").pack()),
        InlineKeyboardButton(text="💰 Купить звёзды", callback_data=MenuCallback(action="buy_manual").pack()),
        width=2
    )
    builder.row(
        InlineKeyboardButton(text="🧮 Калькулятор", callback_data=MenuCallback(action="calculator").pack()),
        InlineKeyboardButton(text="🎰 Мини игры", callback_data=MenuCallback(action="games").pack()),
        width=2
    )
    builder.row(
        InlineKeyboardButton(text="💱 Обмен валют", callback_data=MenuCallback(action="exchange").pack()),
        InlineKeyboardButton(text="📤 Вывод", callback_data=MenuCallback(action="withdraw").pack()),
        width=2
    )
    builder.row(
        InlineKeyboardButton(text="👥 Мои рефералы", callback_data=MenuCallback(action="referrals").pack()),
        InlineKeyboardButton(text="ℹ️ Информация", callback_data=MenuCallback(action="info").pack()),
        width=2
    )
    builder.row(
        InlineKeyboardButton(text="🆘 Поддержка", callback_data=MenuCallback(action="support").pack()),
    )
    return builder.as_markup()

def get_calculator_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="⭐ → ₽", callback_data=MenuCallback(action="calc_stars_to_rub").pack()),
        InlineKeyboardButton(text="₽ → ⭐", callback_data=MenuCallback(action="calc_rub_to_stars").pack()),
        width=2
    )
    builder.row(
        InlineKeyboardButton(text="⬅️ Назад", callback_data=MenuCallback(action="back_to_menu").pack()),
    )
    return builder.as_markup()

def get_back_to_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="⬅️ Назад", callback_data=MenuCallback(action="back_to_menu").pack()),
    )
    return builder.as_markup()

def get_order_action_keyboard(order_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Подтвердить", callback_data=OrderCallback(action="approve", order_id=order_id).pack()),
        InlineKeyboardButton(text="❌ Отклонить", callback_data=OrderCallback(action="reject", order_id=order_id).pack()),
        width=2
    )
    return builder.as_markup()

def get_processed_order_keyboard(status: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if status == 'approved':
        builder.row(InlineKeyboardButton(text="✅ Подтверждено", callback_data="no_action"))
    else:
        builder.row(InlineKeyboardButton(text="❌ Отклонено", callback_data="no_action"))
    return builder.as_markup()

def get_support_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📝 Создать тикет", callback_data="create_ticket"))
    builder.row(InlineKeyboardButton(text="📋 Мои тикеты", callback_data="my_tickets"))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=MenuCallback(action="back_to_menu").pack()))
    return builder.as_markup()

def get_ticket_subjects_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for i, subject in enumerate(TICKET_SUBJECTS):
        builder.row(InlineKeyboardButton(text=subject, callback_data=SubjectCallback(subject_id=i).pack()))
    builder.row(InlineKeyboardButton(text="❌ Отменить создание", callback_data="cancel_ticket"))
    return builder.as_markup()

def get_ticket_action_keyboard(ticket_id: int, is_staff: bool = False) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if is_staff:
        builder.row(
            InlineKeyboardButton(text="📝 Ответить", callback_data=TicketCallback(action="reply", ticket_id=ticket_id).pack()),
            InlineKeyboardButton(text="🔒 Закрыть", callback_data=TicketCallback(action="close", ticket_id=ticket_id).pack()),
            width=2
        )
    else:
        builder.row(
            InlineKeyboardButton(text="📝 Добавить сообщение", callback_data=TicketCallback(action="add_message", ticket_id=ticket_id).pack()),
            InlineKeyboardButton(text="🔒 Закрыть", callback_data=TicketCallback(action="close", ticket_id=ticket_id).pack()),
            width=2
        )
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_tickets"))
    return builder.as_markup()

def get_skip_promocode_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➡️ Пропустить", callback_data="skip_promocode"))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=MenuCallback(action="back_to_menu").pack()))
    return builder.as_markup()

def get_games_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🎯 Мины", callback_data=MenuCallback(action="game_mines").pack()),
        InlineKeyboardButton(text="🎰 Казино", callback_data=MenuCallback(action="game_casino").pack()),
        width=2
    )
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=MenuCallback(action="back_to_menu").pack()))
    return builder.as_markup()

def get_mines_game_keyboard(game_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for i in range(1, 4):
        builder.row(InlineKeyboardButton(
            text=f"Шар {i}",
            callback_data=GameCallback(action="mines_choice", game_id=game_id, choice=i).pack()
        ))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=MenuCallback(action="games").pack()))
    return builder.as_markup()

def get_casino_bet_amount_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for amount in CASINO_BET_AMOUNTS:
        builder.row(InlineKeyboardButton(
            text=f"{amount} ⭐",
            callback_data=GameCallback(action="casino_bet", bet_amount=amount).pack()
        ))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=MenuCallback(action="games").pack()))
    return builder.as_markup()

def get_exchange_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="💰 → 🎮 Реальные → Виртуальные",
        callback_data=ExchangeCallback(action="start", exchange_type="real_to_virtual").pack()
    ))
    builder.row(InlineKeyboardButton(
        text="🎮 → 💰 Виртуальные → Реальные",
        callback_data=ExchangeCallback(action="start", exchange_type="virtual_to_real").pack()
    ))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=MenuCallback(action="back_to_menu").pack()))
    return builder.as_markup()

def get_withdrawal_keyboard(withdrawal_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Одобрить", callback_data=WithdrawalCallback(action="approve", withdrawal_id=withdrawal_id).pack()),
        InlineKeyboardButton(text="❌ Отклонить", callback_data=WithdrawalCallback(action="reject", withdrawal_id=withdrawal_id).pack()),
        width=2
    )
    return builder.as_markup()

def get_subscription_keyboard() -> InlineKeyboardMarkup:
    from config import REQUIRED_CHANNELS
    builder = InlineKeyboardBuilder()
    for channel_id in REQUIRED_CHANNELS:
        try:
            builder.row(InlineKeyboardButton(
                text="📢 Подписаться на канал",
                url=f"https://t.me/c/{str(channel_id)[4:]}"
            ))
        except:
            pass
    builder.row(InlineKeyboardButton(text="✅ Я подписался", callback_data="check_subscription"))
    return builder.as_markup()

def get_stars_amount_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for amount in STARS_PRICES:
        builder.row(InlineKeyboardButton(
            text=f"{amount} ⭐ — {amount} XTR",
            callback_data=StarsPurchaseCallback(amount=amount).pack()
        ))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=MenuCallback(action="back_to_menu").pack()))
    return builder.as_markup()

# ========== ДОБАВЛЕННЫЕ КЛАВИАТУРЫ ДЛЯ ОТМЕНЫ ЗАКАЗА И ОТЗЫВОВ ==========
def get_cancel_reasons_keyboard(order_id: int) -> InlineKeyboardMarkup:
    """Клавиатура с причинами отмены заказа"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="💰 Выбрал не правильную сумму",
        callback_data=f"cancel_reason_wrong_amount"
    ))
    builder.row(InlineKeyboardButton(
        text="👤 Неправильные данные получателя",
        callback_data=f"cancel_reason_wrong_recipient"
    ))
    builder.row(InlineKeyboardButton(
        text="🤷 Передумал",
        callback_data=f"cancel_reason_changed_mind"
    ))
    builder.row(InlineKeyboardButton(
        text="📝 Другая причина",
        callback_data=f"cancel_reason_custom"
    ))
    builder.row(InlineKeyboardButton(
        text="⬅️ Назад",
        callback_data=OrderCallback(action="view", order_id=order_id).pack()
    ))
    return builder.as_markup()

def get_skip_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура с кнопкой 'Пропустить'"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➡️ Пропустить", callback_data="skip"))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=MenuCallback(action="back_to_menu").pack()))
    return builder.as_markup()

def get_rating_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для оценки от 1 до 5 звёзд"""
    builder = InlineKeyboardBuilder()
    for star in range(1, 6):
        builder.row(InlineKeyboardButton(
            text="⭐" * star,
            callback_data=f"rating_{star}"
        ))
    builder.row(InlineKeyboardButton(text="⬅️ Отмена", callback_data=MenuCallback(action="back_to_menu").pack()))
    return builder.as_markup()

# ========== АДМИН-ПАНЕЛЬ ==========
def get_admin_main_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="💰 Экономика", callback_data=AdminCallback(action="economy_menu").pack()),
        InlineKeyboardButton(text="📦 Заказы", callback_data=AdminCallback(action="orders_menu").pack()),
        width=2
    )
    builder.row(
        InlineKeyboardButton(text="🎁 Промокоды", callback_data=AdminCallback(action="promocodes_menu").pack()),
        InlineKeyboardButton(text="📅 Акции", callback_data=AdminCallback(action="sales_menu").pack()),
        width=2
    )
    builder.row(
        InlineKeyboardButton(text="🎂 День рождения", callback_data=AdminCallback(action="birthday_menu").pack()),
        InlineKeyboardButton(text="📋 Шаблоны тикетов", callback_data=AdminCallback(action="templates_menu").pack()),
        width=2
    )
    builder.row(
        InlineKeyboardButton(text="👥 Пользователи", callback_data=AdminCallback(action="users_menu").pack()),
        InlineKeyboardButton(text="📊 Статистика", callback_data=AdminCallback(action="stats_menu").pack()),
        width=2
    )
    builder.row(
        InlineKeyboardButton(text="📢 Рассылка", callback_data=AdminCallback(action="mailing_menu").pack()),
        InlineKeyboardButton(text="📜 Журнал", callback_data=AdminCallback(action="logs_menu").pack()),
        width=2
    )
    builder.row(
        InlineKeyboardButton(text="🏆 Ачивки", callback_data=AdminCallback(action="achievements_menu").pack()),
        InlineKeyboardButton(text="🛠️ Техническое", callback_data=AdminCallback(action="tech_menu").pack()),
        width=2
    )
    builder.row(
        InlineKeyboardButton(text="⚙️ Настройки", callback_data=AdminCallback(action="settings_menu").pack()),
        InlineKeyboardButton(text="⬅️ Выход", callback_data=MenuCallback(action="back_to_menu").pack()),
        width=2
    )
    return builder.as_markup()

def get_back_to_admin_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⬅️ Назад в админку", callback_data=AdminCallback(action="main").pack()))
    return builder.as_markup()

# ----- Экономика -----
def get_economy_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="✏️ Изменить курс", callback_data=AdminCallback(action="edit_star_rate").pack()))
    builder.row(
        InlineKeyboardButton(text="✏️ Комиссия вывода", callback_data=AdminCallback(action="edit_withdraw_commission").pack()),
        InlineKeyboardButton(text="✏️ Комиссия обмена (реал→вирт)", callback_data=AdminCallback(action="edit_exchange_commission_real").pack()),
        width=2
    )
    builder.row(
        InlineKeyboardButton(text="✏️ Комиссия обмена (вирт→реал)", callback_data=AdminCallback(action="edit_exchange_commission_virtual").pack()),
        InlineKeyboardButton(text="✏️ Мин. покупка", callback_data=AdminCallback(action="edit_min_stars").pack()),
        width=2
    )
    builder.row(
        InlineKeyboardButton(text="✏️ Мин. вывод", callback_data=AdminCallback(action="edit_withdraw_min").pack()),
        InlineKeyboardButton(text="Округление", callback_data=AdminCallback(action="toggle_rounding").pack()),
        width=2
    )
    builder.row(
        InlineKeyboardButton(text="💾 Сохранить всё", callback_data=AdminCallback(action="save_economy").pack()),
        InlineKeyboardButton(text="⬅️ Назад", callback_data=AdminCallback(action="main").pack()),
        width=2
    )
    return builder.as_markup()

# ----- Промокоды -----
def get_promocodes_main_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="➕ Создать", callback_data=AdminCallback(action="create_promocode").pack()),
        InlineKeyboardButton(text="📋 Список", callback_data=AdminCallback(action="list_promocodes", page=1).pack()),
        width=2
    )
    builder.row(
        InlineKeyboardButton(text="📊 Статистика", callback_data=AdminCallback(action="promo_stats").pack()),
        InlineKeyboardButton(text="⬅️ Назад", callback_data=AdminCallback(action="main").pack()),
        width=2
    )
    return builder.as_markup()

def get_promocode_actions_keyboard(promo_id: int, page: int = 1) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✏️ Редактировать", callback_data=PromocodeCallback(action="edit", promo_id=promo_id, page=page).pack()),
        InlineKeyboardButton(text="🗑️ Удалить", callback_data=PromocodeCallback(action="delete", promo_id=promo_id, page=page).pack()),
        width=2
    )
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=AdminCallback(action="list_promocodes", page=page).pack()))
    return builder.as_markup()

# ----- Акции -----
def get_sales_main_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="➕ Создать акцию", callback_data=AdminCallback(action="create_sale").pack()),
        InlineKeyboardButton(text="📋 Список акций", callback_data=AdminCallback(action="list_sales", page=1).pack()),
        width=2
    )
    builder.row(
        InlineKeyboardButton(text="🤖 Авто-применение", callback_data=AdminCallback(action="toggle_auto_sale").pack()),
        InlineKeyboardButton(text="⬅️ Назад", callback_data=AdminCallback(action="main").pack()),
        width=2
    )
    return builder.as_markup()

def get_sale_actions_keyboard(sale_id: int, page: int = 1) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✏️ Редактировать", callback_data=AdminCallback(action="edit_sale", target_id=sale_id, page=page).pack()),
        InlineKeyboardButton(text="🗑️ Удалить", callback_data=AdminCallback(action="delete_sale", target_id=sale_id, page=page).pack()),
        width=2
    )
    builder.row(InlineKeyboardButton(text="⏸️ Пауза/Возобновить", callback_data=AdminCallback(action="toggle_sale", target_id=sale_id, page=page).pack()))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=AdminCallback(action="list_sales", page=page).pack()))
    return builder.as_markup()

# ----- День рождения бота -----
def get_birthday_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✏️ Редактировать текст", callback_data=AdminCallback(action="edit_birthday_text").pack()),
        InlineKeyboardButton(text="➕ Заменить фото", callback_data=AdminCallback(action="edit_birthday_photo").pack()),
        width=2
    )
    builder.row(
        InlineKeyboardButton(text="➕ Заменить аудио", callback_data=AdminCallback(action="edit_birthday_audio").pack()),
        InlineKeyboardButton(text="➕ Заменить стикер", callback_data=AdminCallback(action="edit_birthday_sticker").pack()),
        width=2
    )
    builder.row(
        InlineKeyboardButton(text="🎲 Режим отправки", callback_data=AdminCallback(action="birthday_mode").pack()),
        InlineKeyboardButton(text="✅ Включить/⏸️ Выключить", callback_data=AdminCallback(action="toggle_birthday").pack()),
        width=2
    )
    builder.row(
        InlineKeyboardButton(text="💾 Сохранить", callback_data=AdminCallback(action="save_birthday").pack()),
        InlineKeyboardButton(text="⬅️ Назад", callback_data=AdminCallback(action="main").pack()),
        width=2
    )
    return builder.as_markup()

# ----- Шаблоны тикетов -----
def get_templates_main_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="➕ Создать шаблон", callback_data=AdminCallback(action="create_template").pack()),
        InlineKeyboardButton(text="📋 Список шаблонов", callback_data=AdminCallback(action="list_templates", page=1).pack()),
        width=2
    )
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=AdminCallback(action="main").pack()))
    return builder.as_markup()

def get_template_actions_keyboard(template_name: str, page: int = 1) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✏️ Редактировать", callback_data=AdminCallback(action="edit_template", data=template_name, page=page).pack()),
        InlineKeyboardButton(text="🗑️ Удалить", callback_data=AdminCallback(action="delete_template", data=template_name, page=page).pack()),
        width=2
    )
    builder.row(InlineKeyboardButton(text="📋 Копировать", callback_data=AdminCallback(action="copy_template", data=template_name, page=page).pack()))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=AdminCallback(action="list_templates", page=page).pack()))
    return builder.as_markup()

# ----- Пользователи -----
def get_users_main_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔍 Поиск", callback_data=AdminCallback(action="user_search").pack()),
        InlineKeyboardButton(text="❄️ Замороженные", callback_data=AdminCallback(action="list_frozen", page=1).pack()),
        width=2
    )
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=AdminCallback(action="main").pack()))
    return builder.as_markup()

def get_user_actions_keyboard(user_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="❄️ Заморозить", callback_data=UserCallback(action="freeze", user_id=user_id).pack()),
        InlineKeyboardButton(text="🧊 Разморозить", callback_data=UserCallback(action="unfreeze", user_id=user_id).pack()),
        width=2
    )
    builder.row(
        InlineKeyboardButton(text="⭐ Выдать звёзды", callback_data=UserCallback(action="give_stars", user_id=user_id).pack()),
        InlineKeyboardButton(text="📉 Списать звёзды", callback_data=UserCallback(action="deduct_stars", user_id=user_id).pack()),
        width=2
    )
    builder.row(
        InlineKeyboardButton(text="👑 Сменить роль", callback_data=UserCallback(action="change_role", user_id=user_id).pack()),
        InlineKeyboardButton(text="📄 Профиль", callback_data=UserCallback(action="view_profile", user_id=user_id).pack()),
        width=2
    )
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=AdminCallback(action="users_menu").pack()))
    return builder.as_markup()

def get_freeze_reason_keyboard(user_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    reasons = [
        "Неоплаченные заказы (3+)",
        "Подозрительная активность",
        "Нарушение правил",
        "Возврат средств",
        "Другое"
    ]
    for reason in reasons:
        builder.row(InlineKeyboardButton(text=reason, callback_data=UserCallback(action="freeze_reason", user_id=user_id, data=reason).pack()))
    builder.row(InlineKeyboardButton(text="⬅️ Отмена", callback_data=UserCallback(action="cancel_freeze", user_id=user_id).pack()))
    return builder.as_markup()

# ----- Ачивки -----
def get_achievements_main_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="➕ Создать ачивку", callback_data=AdminCallback(action="create_achievement").pack()),
        InlineKeyboardButton(text="📋 Список ачивок", callback_data=AdminCallback(action="list_achievements", page=1).pack()),
        width=2
    )
    builder.row(
        InlineKeyboardButton(text="👤 Выдать пользователю", callback_data=AdminCallback(action="award_achievement_menu").pack()),
        InlineKeyboardButton(text="🗑️ Удалить у пользователя", callback_data=AdminCallback(action="remove_achievement_menu").pack()),
        width=2
    )
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=AdminCallback(action="main").pack()))
    return builder.as_markup()

def get_achievement_actions_keyboard(code: str, page: int = 1) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✏️ Редактировать", callback_data=AchievementCallback(action="edit", code=code, page=page).pack()),
        InlineKeyboardButton(text="👤 Выдать", callback_data=AchievementCallback(action="award", code=code, page=page).pack()),
        width=2
    )
    builder.row(InlineKeyboardButton(text="🗑️ Удалить у всех", callback_data=AchievementCallback(action="delete_global", code=code, page=page).pack()))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=AdminCallback(action="list_achievements", page=page).pack()))
    return builder.as_markup()

# ----- Техническое -----
def get_tech_main_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔧 Режим ТО", callback_data=AdminCallback(action="maintenance_menu").pack()),
        InlineKeyboardButton(text="💾 Бекапы", callback_data=AdminCallback(action="backup_menu").pack()),
        width=2
    )
    builder.row(
        InlineKeyboardButton(text="🗑️ Очистить кэш", callback_data=AdminCallback(action="clear_cache").pack()),
        InlineKeyboardButton(text="📊 Статус системы", callback_data=AdminCallback(action="system_status").pack()),
        width=2
    )
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=AdminCallback(action="main").pack()))
    return builder.as_markup()

def get_maintenance_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔴 Включить", callback_data=AdminCallback(action="maintenance_on").pack()),
        InlineKeyboardButton(text="🟢 Выключить", callback_data=AdminCallback(action="maintenance_off").pack()),
        width=2
    )
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=AdminCallback(action="tech_menu").pack()))
    return builder.as_markup()

def get_backup_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📀 Создать бекап", callback_data=AdminCallback(action="create_backup").pack()),
        InlineKeyboardButton(text="📋 Список бекапов", callback_data=AdminCallback(action="list_backups", page=1).pack()),
        width=2
    )
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=AdminCallback(action="tech_menu").pack()))
    return builder.as_markup()

def get_backup_actions_keyboard(filename: str, page: int = 1) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔄 Восстановить", callback_data=BackupCallback(action="restore", filename=filename, page=page).pack()),
        InlineKeyboardButton(text="🗑️ Удалить", callback_data=BackupCallback(action="delete", filename=filename, page=page).pack()),
        width=2
    )
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=AdminCallback(action="list_backups", page=page).pack()))
    return builder.as_markup()

# ----- Рассылка -----
def get_mailing_main_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📢 Создать рассылку", callback_data=AdminCallback(action="create_mailing").pack()),
        InlineKeyboardButton(text="📊 Статистика рассылок", callback_data=AdminCallback(action="mailing_stats", page=1).pack()),
        width=2
    )
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=AdminCallback(action="main").pack()))
    return builder.as_markup()

def get_mailing_filter_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="👥 ВСЕМ", callback_data=AdminCallback(action="mailing_filter_all").pack()))
    builder.row(InlineKeyboardButton(text="🟢 АКТИВНЫМ (7 дней)", callback_data=AdminCallback(action="mailing_filter_active").pack()))
    builder.row(InlineKeyboardButton(text="🔴 НЕАКТИВНЫМ (>30 дней)", callback_data=AdminCallback(action="mailing_filter_inactive").pack()))
    builder.row(InlineKeyboardButton(text="🏆 ТОП-10 покупателей", callback_data=AdminCallback(action="mailing_filter_top").pack()))
    builder.row(InlineKeyboardButton(text="📋 ВЫБОРОЧНО", callback_data=AdminCallback(action="mailing_filter_custom").pack()))
    builder.row(InlineKeyboardButton(text="🧪 ТЕСТОВЫЙ РЕЖИМ (себе)", callback_data=AdminCallback(action="mailing_filter_test").pack()))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=AdminCallback(action="mailing_menu").pack()))
    return builder.as_markup()

def get_mailing_preview_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Всё хорошо, отправляем", callback_data=AdminCallback(action="mailing_send").pack()),
        InlineKeyboardButton(text="✏️ Редактировать", callback_data=AdminCallback(action="mailing_edit").pack()),
        width=2
    )
    builder.row(InlineKeyboardButton(text="⬅️ Отмена", callback_data=AdminCallback(action="mailing_menu").pack()))
    return builder.as_markup()

# ----- Журнал -----
def get_logs_filter_keyboard(page: int = 1) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="👤 По админу", callback_data=AdminCallback(action="logs_filter_admin", page=page).pack()),
        InlineKeyboardButton(text="🎯 По действию", callback_data=AdminCallback(action="logs_filter_action", page=page).pack()),
        width=2
    )
    builder.row(
        InlineKeyboardButton(text="📅 По дате", callback_data=AdminCallback(action="logs_filter_date", page=page).pack()),
        InlineKeyboardButton(text="🔄 Сбросить", callback_data=AdminCallback(action="logs_reset", page=page).pack()),
        width=2
    )
    builder.row(
        InlineKeyboardButton(text="📥 Экспорт в TXT", callback_data=AdminCallback(action="logs_export", page=page).pack()),
        InlineKeyboardButton(text="⬅️ Назад", callback_data=AdminCallback(action="main").pack()),
        width=2
    )
    return builder.as_markup()

# ----- Настройки -----
def get_settings_main_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="⚙️ Общие настройки", callback_data=AdminCallback(action="settings_general").pack()),
        InlineKeyboardButton(text="💰 Экономика", callback_data=AdminCallback(action="economy_menu").pack()),
        width=2
    )
    builder.row(
        InlineKeyboardButton(text="🎮 Игры", callback_data=AdminCallback(action="settings_games").pack()),
        InlineKeyboardButton(text="🔗 Рефералы", callback_data=AdminCallback(action="settings_referrals").pack()),
        width=2
    )
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=AdminCallback(action="main").pack()))
    return builder.as_markup()

# ----- Пагинация (универсальная) -----
def get_pagination_keyboard(
    current_page: int,
    total_pages: int,
    callback_prefix: str,
    extra_data: Dict[str, Any] = None
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    buttons = []
    if current_page > 1:
        data = {"page": current_page - 1}
        if extra_data:
            data.update(extra_data)
        buttons.append(InlineKeyboardButton(
            text="◀️",
            callback_data=AdminCallback(action=callback_prefix, **data).pack()
        ))
    start = max(1, current_page - 2)
    end = min(total_pages, start + 4)
    for page in range(start, end + 1):
        text = f"·{page}·" if page == current_page else str(page)
        data = {"page": page}
        if extra_data:
            data.update(extra_data)
        buttons.append(InlineKeyboardButton(
            text=text,
            callback_data=AdminCallback(action=callback_prefix, **data).pack()
        ))
    if current_page < total_pages:
        data = {"page": current_page + 1}
        if extra_data:
            data.update(extra_data)
        buttons.append(InlineKeyboardButton(
            text="▶️",
            callback_data=AdminCallback(action=callback_prefix, **data).pack()
        ))
    builder.row(*buttons)
    return builder.as_markup()

# ========== ТИКЕТЫ: МЕНЮ В ГРУППЕ ==========
def get_ticket_group_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🟢 ОТКРЫТЫЕ ТИКЕТЫ", callback_data=TicketCallback(action="group_open", ticket_id=0).pack()))
    builder.row(InlineKeyboardButton(text="🔵 МОИ ТИКЕТЫ (где отвечал)", callback_data=TicketCallback(action="group_my", ticket_id=0).pack()))
    builder.row(InlineKeyboardButton(text="🔍 ПОИСК ПО НОМЕРУ/ЮЗЕРУ", callback_data=TicketCallback(action="group_search", ticket_id=0).pack()))
    builder.row(InlineKeyboardButton(text="📊 МОЯ СТАТИСТИКА", callback_data=TicketCallback(action="group_stats", ticket_id=0).pack()))
    builder.row(InlineKeyboardButton(text="⭐ РЕЙТИНГ ПОДДЕРЖКИ", callback_data=TicketCallback(action="group_rating", ticket_id=0).pack()))
    return builder.as_markup()

def get_ticket_priority_keyboard(ticket_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    priorities = [
        ("🟢 Низкий", "green"),
        ("🟡 Средний", "yellow"),
        ("🔴 Высокий", "red"),
        ("⚫ Критичный", "black")
    ]
    for name, val in priorities:
        builder.row(InlineKeyboardButton(
            text=name,
            callback_data=TicketCallback(action=f"set_priority_{val}", ticket_id=ticket_id).pack()
        ))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=TicketCallback(action="view", ticket_id=ticket_id).pack()))
    return builder.as_markup()

def get_ticket_rating_keyboard(ticket_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for star in range(1, 6):
        builder.row(InlineKeyboardButton(
            text="⭐" * star,
            callback_data=TicketCallback(action=f"rate_{star}", ticket_id=ticket_id).pack()
        ))
    builder.row(InlineKeyboardButton(text="⬅️ Пропустить", callback_data=TicketCallback(action="skip_rating", ticket_id=ticket_id).pack()))
    return builder.as_markup()

# ========== РЕФЕРАЛЫ (ПРОФИЛЬ) ==========
def get_referrals_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📊 Аналитика", callback_data=MenuCallback(action="referral_analytics").pack()),
        InlineKeyboardButton(text="⬅️ Назад в профиль", callback_data=MenuCallback(action="profile").pack()),
        width=2
    )
    return builder.as_markup()

# ========== ОТЗЫВЫ ==========
def get_feedback_order_keyboard(order_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for star in range(1, 6):
        builder.row(InlineKeyboardButton(
            text="⭐" * star,
            callback_data=FeedbackCallback(action=f"rate_{star}", order_id=order_id).pack()
        ))
    builder.row(InlineKeyboardButton(text="⬅️ Отмена", callback_data=MenuCallback(action="profile").pack()))
    return builder.as_markup()

# ========== КНОПКА "NO ACTION" (ЗАГЛУШКА) ==========
def get_no_action_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⏳ Обработано", callback_data="no_action"))
    return builder.as_markup()