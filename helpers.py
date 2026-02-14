# FILE: helpers.py
import logging
import hashlib
import time
import os
import json
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple, Union

from aiocache import Cache
from aiocache.decorators import cached

from config import (
    SCREENSHOTS_DIR, BACKUP_DIR, CACHE_TTL_BALANCE, CACHE_TTL_TOP, CACHE_TTL_STAR_RATE,
    ACTION_TIMEOUT_SECONDS, REQUIRED_CHANNELS
)
from database import (
    get_user, get_star_rate, get_top_buyers_no_admins, clear_settings_cache,
    is_user_banned, is_user_frozen, get_freeze_info, get_ban,
    is_maintenance_mode, get_maintenance_info
)

logger = logging.getLogger(__name__)

# ========== КЭШИРОВАНИЕ ==========
cache = Cache(Cache.MEMORY)

@cached(ttl=CACHE_TTL_BALANCE, key="balance:{user_id}")
async def get_cached_balance(user_id: int, currency: str = 'virtual'):
    user = get_user(user_id)
    if not user:
        return 0
    return user[5] if currency == 'virtual' else user[4]

async def invalidate_balance_cache(user_id: int):
    await cache.delete(f"balance:{user_id}")

@cached(ttl=CACHE_TTL_TOP, key="top_buyers")
async def get_cached_top_buyers(limit: int = 10):
    return get_top_buyers_no_admins(limit)

async def invalidate_top_cache():
    await cache.delete("top_buyers")

@cached(ttl=CACHE_TTL_STAR_RATE, key="star_rate")
async def get_cached_star_rate():
    return get_star_rate()

async def invalidate_settings_cache():
    clear_settings_cache()
    await cache.delete("star_rate")
    await cache.delete("top_buyers")

# ========== ДЕДУПЛИКАЦИЯ ДЕЙСТВИЙ ==========
async def is_duplicate_action(action_id: str, ttl: int = 5) -> bool:
    key = f"action:{action_id}"
    if await cache.exists(key):
        return True
    await cache.set(key, "1", ttl=ttl)
    return False

# ========== MIDDLEWARE ДЛЯ ПРОВЕРКИ БАНА ==========
async def check_ban_middleware(handler, event, data):
    """Middleware для проверки, забанен ли пользователь."""
    from aiogram import types
    
    user_id = None
    if isinstance(event, (types.Message, types.CallbackQuery)):
        user_id = event.from_user.id
    else:
        return await handler(event, data)
    
    # Пропускаем команду /start
    if isinstance(event, types.Message) and event.text and event.text.startswith('/start'):
        return await handler(event, data)
    
    if is_user_banned(user_id):
        ban = get_ban(user_id)
        reason = ban[2] if ban else "Не указана"
        banned_until = ban[4] if ban and len(ban) > 4 else None
        
        text = "🚫 Вы забанены!\n"
        text += f"Причина: {reason}\n"
        if banned_until:
            try:
                banned_until_dt = datetime.strptime(banned_until, '%Y-%m-%d %H:%M:%S')
                text += f"Бан истекает: {format_datetime(banned_until_dt)}"
            except:
                text += f"Бан навсегда"
        else:
            text += "Бан навсегда"
        
        if isinstance(event, types.Message):
            await event.answer(text)
        elif isinstance(event, types.CallbackQuery):
            await event.answer(text, show_alert=True)
        return
    
    return await handler(event, data)

# ========== MIDDLEWARE ДЛЯ ПРОВЕРКИ ТЕХНИЧЕСКИХ РАБОТ ==========
async def check_maintenance_middleware(handler, event, data):
    """Middleware для проверки режима технических работ."""
    from aiogram import types
    from helpers import has_access
    
    if not is_maintenance_mode():
        return await handler(event, data)
    
    user_id = None
    if isinstance(event, (types.Message, types.CallbackQuery)):
        user_id = event.from_user.id
    
    # Админы и владелец могут работать в режиме ТО
    if user_id and has_access(user_id, 'admin'):
        return await handler(event, data)
    
    info = get_maintenance_info()
    reason = info.get('reason', 'Плановые работы')
    duration = info.get('duration', '15 минут')
    
    text = (
        "🔧 <b>Ведутся технические работы</b>\n\n"
        f"📋 Причина: {reason}\n"
        f"⏳ Ориентировочно: {duration}\n\n"
        "Приносим извинения за неудобства!\n"
        "Попробуйте зайти позже."
    )
    
    if isinstance(event, types.Message):
        await event.answer(text)
    elif isinstance(event, types.CallbackQuery):
        await event.answer("🔧 Технические работы", show_alert=True)
        await event.message.answer(text)
    
    return None

# ========== MIDDLEWARE ДЛЯ ПРОВЕРКИ ЗАМОРОЗКИ ==========
async def check_freeze_middleware(handler, event, data):
    """Middleware для проверки, заморожен ли пользователь."""
    from aiogram import types
    from helpers import has_access
    
    user_id = None
    if isinstance(event, (types.Message, types.CallbackQuery)):
        user_id = event.from_user.id
    else:
        return await handler(event, data)
    
    # Админы не блокируются заморозкой
    if user_id and has_access(user_id, 'admin'):
        return await handler(event, data)
    
    # Пропускаем команду /start и /support
    if isinstance(event, types.Message):
        if event.text and event.text.startswith(('/start', '/support')):
            return await handler(event, data)
    
    if is_user_frozen(user_id):
        freeze_info = get_freeze_info(user_id)
        reason = freeze_info[0] if freeze_info else "Не указана"
        date = freeze_info[1] if freeze_info else "Неизвестно"
        
        text = (
            f"❄️ <b>ВАШ АККАУНТ ЗАМОРОЖЕН</b>\n\n"
            f"🧊 Причина: {reason}\n"
            f"📅 Дата заморозки: {format_datetime(date)}\n\n"
            f"Для разморозки обратитесь в поддержку: /support"
        )
        
        if isinstance(event, types.Message):
            await event.answer(text)
        elif isinstance(event, types.CallbackQuery):
            await event.answer("❌ Ваш аккаунт заморожен", show_alert=True)
        return
    
    return await handler(event, data)

# ========== ФУНКЦИИ ДЛЯ ПРОВЕРКИ ПРАВ ДОСТУПА ==========
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

# ========== ФОРМАТИРОВАНИЕ ДАТЫ ==========
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

# ========== ОТОБРАЖЕНИЕ РОЛИ ==========
def get_role_display(role: str) -> str:
    from config import ROLE_NAMES
    return ROLE_NAMES.get(role, '👤 Обычный пользователь')

def check_permission(role: str, required_role: str) -> bool:
    role_hierarchy = ['user', 'agent', 'moder', 'admin', 'tech_admin', 'owner']
    try:
        return role_hierarchy.index(role) >= role_hierarchy.index(required_role)
    except ValueError:
        return False

# ========== ГЕНЕРАЦИЯ РЕФЕРАЛЬНОГО КОДА ==========
def generate_referral_code(user_id: int) -> str:
    code = hashlib.md5(f"ref_{user_id}_{time.time()}".encode()).hexdigest()[:8].upper()
    return code

# ========== ФОРМАТИРОВАНИЕ ЦЕН И ЗВЁЗД ==========
def format_price(price: float) -> str:
    return f"{price:.2f}"

def format_stars(amount: int) -> str:
    return f"{amount} ⭐"

# ========== РАБОТА С ФАЙЛАМИ ==========
def ensure_screenshots_dir():
    if not os.path.exists(SCREENSHOTS_DIR):
        os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

def get_screenshot_path(user_id: int, filename: str = None) -> str:
    ensure_screenshots_dir()
    if filename:
        return os.path.join(SCREENSHOTS_DIR, filename)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return os.path.join(SCREENSHOTS_DIR, f"{user_id}_{timestamp}.jpg")

# ========== РАСЧЁТЫ ==========
def calculate_total_price(amount: int, star_rate: float) -> float:
    return amount * star_rate

def calculate_final_price(total_price: float, discount_percent: float = 0) -> float:
    if discount_percent > 0:
        discount = total_price * discount_percent / 100
        return total_price - discount
    return total_price

def calculate_virtual_to_real(virtual_amount: int, rate: float, commission: float) -> Tuple[int, int]:
    real_amount = virtual_amount * rate
    commission_amount = real_amount * commission
    final_amount = real_amount - commission_amount
    return int(final_amount), int(commission_amount)

def calculate_real_to_virtual(real_amount: int, rate: float, commission: float) -> Tuple[int, int]:
    virtual_amount = real_amount * rate
    commission_amount = virtual_amount * commission
    final_amount = virtual_amount - commission_amount
    return int(final_amount), int(commission_amount)

# ========== ВАЛИДАЦИЯ ==========
def validate_username(username: str) -> str:
    if not username:
        return ""
    username = username.strip()
    if not username.startswith('@'):
        username = '@' + username
    username = username.replace(' ', '')
    return username

def truncate_text(text: str, max_length: int = 100) -> str:
    if len(text) <= max_length:
        return text
    return text[:max_length-3] + "..."

def safe_int(value, default=0):
    try:
        return int(value)
    except (ValueError, TypeError):
        return default

def safe_float(value, default=0.0):
    try:
        return float(value)
    except (ValueError, TypeError):
        return default

# ========== ФОРМАТИРОВАНИЕ ПОЛЬЗОВАТЕЛЯ ==========
def format_user_info(user_data: tuple) -> dict:
    if not user_data:
        return {}
    try:
        return {
            'id': user_data[0],
            'user_id': user_data[1],
            'username': user_data[2] or "без юзернейма",
            'full_name': user_data[3] or "Неизвестно",
            'balance': user_data[4] or 0,
            'virtual_balance': user_data[5] or 0,
            'total_spent': user_data[6] or 0.0,
            'role': user_data[7] if len(user_data) > 7 else 'user',
            'referral_code': user_data[8] if len(user_data) > 8 else None,
            'referrer_id': user_data[9] if len(user_data) > 9 else None,
            'created_at': user_data[10] if len(user_data) > 10 else None,
            'last_action': user_data[11] if len(user_data) > 11 else None
        }
    except IndexError:
        logger.error(f"Ошибка форматирования пользователя: {user_data}")
        return {}

def get_user_display_name(user_data: tuple) -> str:
    if not user_data:
        return "Неизвестно"
    try:
        username = user_data[2]
        full_name = user_data[3]
        if username:
            return f"@{username}"
        elif full_name:
            return full_name
        else:
            return f"ID: {user_data[1]}"
    except IndexError:
        return "Неизвестно"

# ========== РЕФЕРАЛЬНЫЕ ВЫПЛАТЫ ==========
def calculate_referral_reward(amount: float, percent: float) -> float:
    return amount * percent / 100

# ========== ФОРМАТИРОВАНИЕ ДЛИТЕЛЬНОСТИ ==========
def format_duration(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds} сек"
    elif seconds < 3600:
        minutes = seconds // 60
        return f"{minutes} мин"
    elif seconds < 86400:
        hours = seconds // 3600
        return f"{hours} час"
    else:
        days = seconds // 86400
        return f"{days} дн"

def validate_amount(amount, min_amount=0, max_amount=None):
    try:
        amount = int(amount)
        if amount < min_amount:
            return False, f"Сумма должна быть не менее {min_amount}"
        if max_amount is not None and amount > max_amount:
            return False, f"Сумма должна быть не более {max_amount}"
        return True, amount
    except ValueError:
        return False, "Сумма должна быть целым числом"

# ========== ЭКРАНИРОВАНИЕ MARKDOWN ==========
def escape_markdown(text: str) -> str:
    if not text:
        return ""
    escape_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in escape_chars:
        text = text.replace(char, f'\\{char}')
    return text

# ========== РАЗМЕР ФАЙЛА ==========
def format_file_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} Б"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} КБ"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} МБ"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} ГБ"

# ========== ПРОВЕРКА ИЗОБРАЖЕНИЙ ==========
def is_valid_image_file(filename: str) -> bool:
    valid_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']
    filename_lower = filename.lower()
    return any(filename_lower.endswith(ext) for ext in valid_extensions)

# ========== УНИКАЛЬНЫЙ ID ==========
def generate_unique_id() -> str:
    return str(uuid.uuid4())

# ========== ПАРСИНГ ВРЕМЕНИ ==========
def parse_time_string(time_str: str) -> int:
    try:
        if time_str.endswith('h'):
            hours = int(time_str[:-1])
            return hours * 3600
        elif time_str.endswith('d'):
            days = int(time_str[:-1])
            return days * 86400
        elif time_str.endswith('m'):
            minutes = int(time_str[:-1])
            return minutes * 60
        elif time_str.endswith('s'):
            seconds = int(time_str[:-1])
            return seconds
        else:
            hours = int(time_str)
            return hours * 3600
    except ValueError:
        return 0

# ========== ОЧИСТКА ТЕЛЕФОНА ==========
def clean_phone_number(phone: str) -> str:
    if not phone:
        return ""
    cleaned = ''.join(filter(str.isdigit, phone))
    if cleaned.startswith('8') and len(cleaned) == 11:
        cleaned = '7' + cleaned[1:]
    if cleaned and not cleaned.startswith('+'):
        cleaned = '+' + cleaned
    return cleaned

# ========== ФОРМАТИРОВАНИЕ СПИСКА ==========
def format_list(items: list, max_items: int = 10) -> str:
    if not items:
        return "Список пуст"
    if len(items) > max_items:
        displayed = items[:max_items]
        remaining = len(items) - max_items
        return "\n".join([f"{i+1}. {item}" for i, item in enumerate(displayed)]) + f"\n\n...и еще {remaining}"
    return "\n".join([f"{i+1}. {item}" for i, item in enumerate(items)])

# ========== ИМЯ ФАЙЛА ДЛЯ БЕКАПА ==========
def create_backup_filename() -> str:
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return f"backup_{timestamp}.db"

# ========== ПРОВЕРКА ВЫХОДНОГО ==========
def is_weekend() -> bool:
    today = datetime.now().weekday()
    return today >= 5

# ========== СРЕДНЕЕ ЗНАЧЕНИЕ ==========
def calculate_average(numbers: list) -> float:
    if not numbers:
        return 0.0
    return sum(numbers) / len(numbers)    await cache.delete(f"balance:{user_id}")

@cached(ttl=CACHE_TTL_TOP, key="top_buyers")
async def get_cached_top_buyers(limit: int = 10):
    return get_top_buyers_no_admins(limit)

async def invalidate_top_cache():
    await cache.delete("top_buyers")

@cached(ttl=CACHE_TTL_STAR_RATE, key="star_rate")
async def get_cached_star_rate():
    return get_star_rate()

async def invalidate_settings_cache():
    clear_settings_cache()
    await cache.delete("star_rate")
    await cache.delete("top_buyers")

# ========== ДЕДУПЛИКАЦИЯ ДЕЙСТВИЙ ==========
async def is_duplicate_action(action_id: str, ttl: int = 5) -> bool:
    key = f"action:{action_id}"
    if await cache.exists(key):
        return True
    await cache.set(key, "1", ttl=ttl)
    return False

# ========== MIDDLEWARE ДЛЯ ПРОВЕРКИ БАНА ==========
async def check_ban_middleware(handler, event, data):
    """Middleware для проверки, забанен ли пользователь."""
    from aiogram import types
    
    user_id = None
    if isinstance(event, (types.Message, types.CallbackQuery)):
        user_id = event.from_user.id
    else:
        return await handler(event, data)
    
    # Пропускаем команду /start
    if isinstance(event, types.Message) and event.text and event.text.startswith('/start'):
        return await handler(event, data)
    
    if is_user_banned(user_id):
        ban = get_ban(user_id)
        reason = ban[2] if ban else "Не указана"
        banned_until = ban[4] if ban and len(ban) > 4 else None
        
        text = "🚫 Вы забанены!\n"
        text += f"Причина: {reason}\n"
        if banned_until:
            try:
                banned_until_dt = datetime.strptime(banned_until, '%Y-%m-%d %H:%M:%S')
                text += f"Бан истекает: {format_datetime(banned_until_dt)}"
            except:
                text += f"Бан навсегда"
        else:
            text += "Бан навсегда"
        
        if isinstance(event, types.Message):
            await event.answer(text)
        elif isinstance(event, types.CallbackQuery):
            await event.answer(text, show_alert=True)
        return
    
    return await handler(event, data)

# ========== MIDDLEWARE ДЛЯ ПРОВЕРКИ ТЕХНИЧЕСКИХ РАБОТ ==========
async def check_maintenance_middleware(handler, event, data):
    """Middleware для проверки режима технических работ."""
    from aiogram import types
    from utils import has_access
    
    if not is_maintenance_mode():
        return await handler(event, data)
    
    user_id = None
    if isinstance(event, (types.Message, types.CallbackQuery)):
        user_id = event.from_user.id
    
    # Админы и владелец могут работать в режиме ТО
    if user_id and has_access(user_id, 'admin'):
        return await handler(event, data)
    
    info = get_maintenance_info()
    reason = info.get('reason', 'Плановые работы')
    duration = info.get('duration', '15 минут')
    
    text = (
        "🔧 <b>Ведутся технические работы</b>\n\n"
        f"📋 Причина: {reason}\n"
        f"⏳ Ориентировочно: {duration}\n\n"
        "Приносим извинения за неудобства!\n"
        "Попробуйте зайти позже."
    )
    
    if isinstance(event, types.Message):
        await event.answer(text)
    elif isinstance(event, types.CallbackQuery):
        await event.answer("🔧 Технические работы", show_alert=True)
        await event.message.answer(text)
    
    return None

# ========== MIDDLEWARE ДЛЯ ПРОВЕРКИ ЗАМОРОЗКИ ==========
async def check_freeze_middleware(handler, event, data):
    """Middleware для проверки, заморожен ли пользователь."""
    from aiogram import types
    from utils import has_access
    
    user_id = None
    if isinstance(event, (types.Message, types.CallbackQuery)):
        user_id = event.from_user.id
    else:
        return await handler(event, data)
    
    # Админы не блокируются заморозкой
    if user_id and has_access(user_id, 'admin'):
        return await handler(event, data)
    
    # Пропускаем команду /start и /support
    if isinstance(event, types.Message):
        if event.text and event.text.startswith(('/start', '/support')):
            return await handler(event, data)
    
    if is_user_frozen(user_id):
        freeze_info = get_freeze_info(user_id)
        reason = freeze_info[0] if freeze_info else "Не указана"
        date = freeze_info[1] if freeze_info else "Неизвестно"
        
        text = (
            f"❄️ <b>ВАШ АККАУНТ ЗАМОРОЖЕН</b>\n\n"
            f"🧊 Причина: {reason}\n"
            f"📅 Дата заморозки: {format_datetime(date)}\n\n"
            f"Для разморозки обратитесь в поддержку: /support"
        )
        
        if isinstance(event, types.Message):
            await event.answer(text)
        elif isinstance(event, types.CallbackQuery):
            await event.answer("❌ Ваш аккаунт заморожен", show_alert=True)
        return
    
    return await handler(event, data)

# ========== ФУНКЦИИ ДЛЯ ПРОВЕРКИ ПРАВ ДОСТУПА ==========
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

# ========== ФОРМАТИРОВАНИЕ ДАТЫ ==========
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

# ========== ОТОБРАЖЕНИЕ РОЛИ ==========
def get_role_display(role: str) -> str:
    from config import ROLE_NAMES
    return ROLE_NAMES.get(role, '👤 Обычный пользователь')

def check_permission(role: str, required_role: str) -> bool:
    role_hierarchy = ['user', 'agent', 'moder', 'admin', 'tech_admin', 'owner']
    try:
        return role_hierarchy.index(role) >= role_hierarchy.index(required_role)
    except ValueError:
        return False

# ========== ГЕНЕРАЦИЯ РЕФЕРАЛЬНОГО КОДА ==========
def generate_referral_code(user_id: int) -> str:
    code = hashlib.md5(f"ref_{user_id}_{time.time()}".encode()).hexdigest()[:8].upper()
    return code

# ========== ФОРМАТИРОВАНИЕ ЦЕН И ЗВЁЗД ==========
def format_price(price: float) -> str:
    return f"{price:.2f}"

def format_stars(amount: int) -> str:
    return f"{amount} ⭐"

# ========== РАБОТА С ФАЙЛАМИ ==========
def ensure_screenshots_dir():
    if not os.path.exists(SCREENSHOTS_DIR):
        os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

def get_screenshot_path(user_id: int, filename: str = None) -> str:
    ensure_screenshots_dir()
    if filename:
        return os.path.join(SCREENSHOTS_DIR, filename)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return os.path.join(SCREENSHOTS_DIR, f"{user_id}_{timestamp}.jpg")

# ========== РАСЧЁТЫ ==========
def calculate_total_price(amount: int, star_rate: float) -> float:
    return amount * star_rate

def calculate_final_price(total_price: float, discount_percent: float = 0) -> float:
    if discount_percent > 0:
        discount = total_price * discount_percent / 100
        return total_price - discount
    return total_price

def calculate_virtual_to_real(virtual_amount: int, rate: float, commission: float) -> Tuple[int, int]:
    real_amount = virtual_amount * rate
    commission_amount = real_amount * commission
    final_amount = real_amount - commission_amount
    return int(final_amount), int(commission_amount)

def calculate_real_to_virtual(real_amount: int, rate: float, commission: float) -> Tuple[int, int]:
    virtual_amount = real_amount * rate
    commission_amount = virtual_amount * commission
    final_amount = virtual_amount - commission_amount
    return int(final_amount), int(commission_amount)

# ========== ВАЛИДАЦИЯ ==========
def validate_username(username: str) -> str:
    if not username:
        return ""
    username = username.strip()
    if not username.startswith('@'):
        username = '@' + username
    username = username.replace(' ', '')
    return username

def truncate_text(text: str, max_length: int = 100) -> str:
    if len(text) <= max_length:
        return text
    return text[:max_length-3] + "..."

def safe_int(value, default=0):
    try:
        return int(value)
    except (ValueError, TypeError):
        return default

def safe_float(value, default=0.0):
    try:
        return float(value)
    except (ValueError, TypeError):
        return default

# ========== ФОРМАТИРОВАНИЕ ПОЛЬЗОВАТЕЛЯ ==========
def format_user_info(user_data: tuple) -> dict:
    if not user_data:
        return {}
    try:
        return {
            'id': user_data[0],
            'user_id': user_data[1],
            'username': user_data[2] or "без юзернейма",
            'full_name': user_data[3] or "Неизвестно",
            'balance': user_data[4] or 0,
            'virtual_balance': user_data[5] or 0,
            'total_spent': user_data[6] or 0.0,
            'role': user_data[7] if len(user_data) > 7 else 'user',
            'referral_code': user_data[8] if len(user_data) > 8 else None,
            'referrer_id': user_data[9] if len(user_data) > 9 else None,
            'created_at': user_data[10] if len(user_data) > 10 else None,
            'last_action': user_data[11] if len(user_data) > 11 else None
        }
    except IndexError:
        logger.error(f"Ошибка форматирования пользователя: {user_data}")
        return {}

def get_user_display_name(user_data: tuple) -> str:
    if not user_data:
        return "Неизвестно"
    try:
        username = user_data[2]
        full_name = user_data[3]
        if username:
            return f"@{username}"
        elif full_name:
            return full_name
        else:
            return f"ID: {user_data[1]}"
    except IndexError:
        return "Неизвестно"

# ========== РЕФЕРАЛЬНЫЕ ВЫПЛАТЫ ==========
def calculate_referral_reward(amount: float, percent: float) -> float:
    return amount * percent / 100

# ========== ФОРМАТИРОВАНИЕ ДЛИТЕЛЬНОСТИ ==========
def format_duration(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds} сек"
    elif seconds < 3600:
        minutes = seconds // 60
        return f"{minutes} мин"
    elif seconds < 86400:
        hours = seconds // 3600
        return f"{hours} час"
    else:
        days = seconds // 86400
        return f"{days} дн"

def validate_amount(amount, min_amount=0, max_amount=None):
    try:
        amount = int(amount)
        if amount < min_amount:
            return False, f"Сумма должна быть не менее {min_amount}"
        if max_amount is not None and amount > max_amount:
            return False, f"Сумма должна быть не более {max_amount}"
        return True, amount
    except ValueError:
        return False, "Сумма должна быть целым числом"

# ========== ЭКРАНИРОВАНИЕ MARKDOWN ==========
def escape_markdown(text: str) -> str:
    if not text:
        return ""
    escape_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in escape_chars:
        text = text.replace(char, f'\\{char}')
    return text

# ========== РАЗМЕР ФАЙЛА ==========
def format_file_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} Б"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} КБ"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} МБ"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} ГБ"

# ========== ПРОВЕРКА ИЗОБРАЖЕНИЙ ==========
def is_valid_image_file(filename: str) -> bool:
    valid_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']
    filename_lower = filename.lower()
    return any(filename_lower.endswith(ext) for ext in valid_extensions)

# ========== УНИКАЛЬНЫЙ ID ==========
def generate_unique_id() -> str:
    return str(uuid.uuid4())

# ========== ПАРСИНГ ВРЕМЕНИ ==========
def parse_time_string(time_str: str) -> int:
    try:
        if time_str.endswith('h'):
            hours = int(time_str[:-1])
            return hours * 3600
        elif time_str.endswith('d'):
            days = int(time_str[:-1])
            return days * 86400
        elif time_str.endswith('m'):
            minutes = int(time_str[:-1])
            return minutes * 60
        elif time_str.endswith('s'):
            seconds = int(time_str[:-1])
            return seconds
        else:
            hours = int(time_str)
            return hours * 3600
    except ValueError:
        return 0

# ========== ОЧИСТКА ТЕЛЕФОНА ==========
def clean_phone_number(phone: str) -> str:
    if not phone:
        return ""
    cleaned = ''.join(filter(str.isdigit, phone))
    if cleaned.startswith('8') and len(cleaned) == 11:
        cleaned = '7' + cleaned[1:]
    if cleaned and not cleaned.startswith('+'):
        cleaned = '+' + cleaned
    return cleaned

# ========== ФОРМАТИРОВАНИЕ СПИСКА ==========
def format_list(items: list, max_items: int = 10) -> str:
    if not items:
        return "Список пуст"
    if len(items) > max_items:
        displayed = items[:max_items]
        remaining = len(items) - max_items
        return "\n".join([f"{i+1}. {item}" for i, item in enumerate(displayed)]) + f"\n\n...и еще {remaining}"
    return "\n".join([f"{i+1}. {item}" for i, item in enumerate(items)])

# ========== ИМЯ ФАЙЛА ДЛЯ БЕКАПА ==========
def create_backup_filename() -> str:
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return f"backup_{timestamp}.db"

# ========== ПРОВЕРКА ВЫХОДНОГО ==========
def is_weekend() -> bool:
    today = datetime.now().weekday()
    return today >= 5

# ========== СРЕДНЕЕ ЗНАЧЕНИЕ ==========
def calculate_average(numbers: list) -> float:
    if not numbers:
        return 0.0
    return sum(numbers) / len(numbers)
