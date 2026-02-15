# FILE: database.py
import sqlite3
import logging
import uuid
import json
import time
import os
import shutil
import glob
import random
import string
from datetime import datetime, timedelta
from contextlib import contextmanager
from config import *

logger = logging.getLogger(__name__)

# ========== IN-MEMORY CACHE ==========
_cache = {}
_cache_ttl = {}

def cache_get(key: str):
    if key in _cache and key in _cache_ttl:
        if time.time() < _cache_ttl[key]:
            return _cache[key]
        else:
            del _cache[key]
            del _cache_ttl[key]
    return None

def cache_set(key: str, value, ttl: int = 60):
    _cache[key] = value
    _cache_ttl[key] = time.time() + ttl

def cache_delete(key: str):
    if key in _cache:
        del _cache[key]
    if key in _cache_ttl:
        del _cache_ttl[key]

def cache_clear():
    _cache.clear()
    _cache_ttl.clear()

def get_db_connection():
    return sqlite3.connect(DATABASE_NAME)

# ========== ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ (ВСЕ ТАБЛИЦЫ) ==========
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # --- СУЩЕСТВУЮЩИЕ ТАБЛИЦЫ ---
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE,
            username TEXT,
            full_name TEXT,
            balance INTEGER DEFAULT 0,
            virtual_balance INTEGER DEFAULT 0,
            total_spent REAL DEFAULT 0,
            role TEXT DEFAULT 'user',
            referral_code TEXT UNIQUE,
            referrer_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_action TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS promocodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE,
            discount_percent INTEGER DEFAULT 0,
            max_uses INTEGER DEFAULT 1,
            used_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount INTEGER,
            recipient_username TEXT,
            screenshot_path TEXT,
            status TEXT DEFAULT 'pending',
            total_price REAL,
            promocode_id INTEGER,
            discount REAL DEFAULT 0,
            comment TEXT,
            canceled_reason TEXT,
            canceled_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id),
            FOREIGN KEY (promocode_id) REFERENCES promocodes (id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS purchase_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            order_id INTEGER,
            amount INTEGER,
            total_price REAL,
            purchase_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id),
            FOREIGN KEY (order_id) REFERENCES orders (id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            subject TEXT DEFAULT 'Другой вопрос',
            status TEXT DEFAULT 'open',
            topic_id INTEGER,
            topic_name TEXT,
            priority TEXT DEFAULT '🟢',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            closed_at TIMESTAMP,
            closed_by INTEGER,
            rating INTEGER,
            rating_comment TEXT,
            agent_id INTEGER,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ticket_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER,
            user_id INTEGER,
            message TEXT,
            is_from_support BOOLEAN DEFAULT 0,
            media_type TEXT,
            file_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (ticket_id) REFERENCES tickets (id),
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS warns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            reason TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            moderator_id INTEGER,
            FOREIGN KEY (user_id) REFERENCES users (user_id),
            FOREIGN KEY (moderator_id) REFERENCES users (user_id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE,
            reason TEXT,
            banned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            banned_until TIMESTAMP,
            moderator_id INTEGER,
            FOREIGN KEY (user_id) REFERENCES users (user_id),
            FOREIGN KEY (moderator_id) REFERENCES users (user_id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS used_promocodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            promocode_id INTEGER,
            order_id INTEGER,
            used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id),
            FOREIGN KEY (promocode_id) REFERENCES promocodes (id),
            FOREIGN KEY (order_id) REFERENCES orders (id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS games (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id TEXT UNIQUE,
            user_id INTEGER,
            game_type TEXT,
            bet_amount INTEGER,
            win_amount INTEGER DEFAULT 0,
            result TEXT,
            dice_message_id INTEGER,
            processed BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS withdrawals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            withdrawal_id TEXT UNIQUE,
            user_id INTEGER,
            amount INTEGER,
            payout_amount INTEGER,
            status TEXT DEFAULT 'pending',
            screenshot_path TEXT,
            recipient_username TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            processed_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS exchanges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exchange_id TEXT UNIQUE,
            user_id INTEGER,
            from_currency TEXT,
            to_currency TEXT,
            amount INTEGER,
            converted_amount INTEGER,
            commission INTEGER,
            recipient_username TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS processed_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action_id TEXT UNIQUE,
            user_id INTEGER,
            action_type TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS referral_rewards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            referrer_id INTEGER,
            referred_id INTEGER,
            purchase_id INTEGER,
            amount INTEGER,
            currency TEXT DEFAULT 'virtual',
            paid BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (referrer_id) REFERENCES users (user_id),
            FOREIGN KEY (referred_id) REFERENCES users (user_id),
            FOREIGN KEY (purchase_id) REFERENCES purchase_history (id),
            UNIQUE(referred_id, purchase_id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS subscription_checks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE,
            subscribed BOOLEAN DEFAULT 0,
            last_check TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS referral_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            referrer_id INTEGER,
            referred_id INTEGER,
            referred_username TEXT,
            referred_full_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (referrer_id) REFERENCES users (user_id),
            FOREIGN KEY (referred_id) REFERENCES users (user_id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stars_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount INTEGER NOT NULL,
            charge_id TEXT UNIQUE,
            payload TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')

    # --- НОВЫЕ ТАБЛИЦЫ ---
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS achievements_list (
            code TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            icon TEXT DEFAULT '🏆',
            hidden BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_achievements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            ach_code TEXT NOT NULL,
            earned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, ach_code),
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            FOREIGN KEY (ach_code) REFERENCES achievements_list(code)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS discount_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE,
            discount_percent INTEGER,
            max_uses INTEGER DEFAULT 1,
            used_count INTEGER DEFAULT 0,
            expires_at TIMESTAMP,
            comment TEXT,
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_discounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            discount_percent INTEGER,
            source_link TEXT,
            applied_to_order_id INTEGER,
            expires_at TIMESTAMP,
            used BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, source_link)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS freezes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE,
            reason TEXT NOT NULL,
            frozen_by INTEGER,
            frozen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admin_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id INTEGER NOT NULL,
            admin_username TEXT,
            action_type TEXT NOT NULL,
            target_type TEXT,
            target_id INTEGER,
            details TEXT,
            ip TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_admin_logs_admin ON admin_logs(admin_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_admin_logs_type ON admin_logs(action_type)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_admin_logs_date ON admin_logs(created_at)')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            order_id INTEGER NOT NULL UNIQUE,
            rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
            text TEXT,
            photo_id TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            FOREIGN KEY (order_id) REFERENCES orders(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ticket_ratings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER NOT NULL UNIQUE,
            user_id INTEGER NOT NULL,
            agent_id INTEGER NOT NULL,
            rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
            comment TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (ticket_id) REFERENCES tickets(id),
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            FOREIGN KEY (agent_id) REFERENCES users(user_id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS mailings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id INTEGER,
            filter_type TEXT,
            text TEXT,
            media_file_id TEXT,
            media_type TEXT,
            button_text TEXT,
            button_url TEXT,
            scheduled_at TIMESTAMP,
            status TEXT DEFAULT 'pending',
            total_count INTEGER,
            sent_count INTEGER DEFAULT 0,
            fail_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # --- Базовые ачивки ---
    cursor.execute('''
        INSERT OR IGNORE INTO achievements_list (code, name, description, icon) VALUES
        ('first_purchase', '🆕 Новичок', 'Сделал первую покупку', '🆕'),
        ('economy', '💰 Эконом', 'Сэкономил 500₽ по промокодам', '💰'),
        ('referrer_10', '🤝 Друг народа', 'Пригласил 10 рефералов', '🤝'),
        ('spent_50k', '👑 Магнат', 'Потратил 50 000₽', '👑'),
        ('games_100', '🎲 Азартный', 'Сыграл 100 игр в казино', '🎲'),
        ('mines_10_streak', '🎯 Снайпер', 'Выиграл в "Мины" 10 раз подряд', '🎯'),
        ('fast_buy', '⚡ Скорость', 'Купил звёзды за 1 минуту после старта', '⚡'),
        ('night_10', '🌙 Ночной гость', '10 покупок с 00:00 до 06:00', '🌙'),
        ('veteran_1year', '🚀 Ветеран', '1 год с ботом', '🚀'),
        ('screenshots_5', '📸 Фотограф', '5 успешных скриншотов оплаты', '📸'),
        ('birthday_buy', '🎂 Именинник', 'Купил в день рождения', '🎂'),
        ('share_link', '📢 Репостер', 'Поделился ссылкой на бота', '📢')
    ''')

    # --- Настройки по умолчанию ---
    cursor.execute("SELECT COUNT(*) FROM settings")
    if cursor.fetchone()[0] == 0:
        default_settings = [
            ('star_rate', str(STAR_RATE)),
            ('min_stars', str(MIN_STARS)),
            ('virtual_to_real_rate', str(VIRTUAL_TO_REAL_RATE)),
            ('real_to_virtual_rate', str(REAL_TO_VIRTUAL_RATE)),
            ('real_to_virtual_min', str(REAL_TO_VIRTUAL_MIN)),
            ('withdraw_min_real', str(WITHDRAW_MIN_REAL)),
            ('withdraw_commission', str(WITHDRAW_COMMISSION)),
            ('exchange_commission', str(EXCHANGE_COMMISSION)),
            ('rounding_enabled', '1'),
            ('birthday_date', ''),
            ('birthday_enabled', '0'),
            ('birthday_text', ''),
            ('birthday_photo', ''),
            ('birthday_audio', ''),
            ('birthday_sticker', ''),
            ('birthday_mode', 'random'),
            ('maintenance_mode', '0'),
            ('maintenance_reason', ''),
            ('maintenance_until', ''),
            ('auto_backup_interval', '6'),
            ('backup_keep_count', '7'),
            ('referral_levels', json.dumps([
                {"min": 0, "max": 5, "percent": 5, "name": "Бронзовый"},
                {"min": 5, "max": 20, "percent": 7, "name": "Серебряный"},
                {"min": 20, "max": 999999, "percent": 10, "name": "Золотой"}
            ]))
        ]
        cursor.executemany(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            default_settings
        )

    conn.commit()
    conn.close()
    logger.info("База данных инициализирована/обновлена")

# ========== ОСНОВНЫЕ ФУНКЦИИ ==========

def get_user(user_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user

def create_user(user_id: int, username: str, full_name: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO users (user_id, username, full_name) VALUES (?, ?, ?)",
            (user_id, username, full_name)
        )
        conn.commit()
        logger.info(f"Создан пользователь: {user_id}, {username}, {full_name}")
    except sqlite3.IntegrityError:
        cursor.execute(
            "UPDATE users SET username = ?, full_name = ? WHERE user_id = ?",
            (username, full_name, user_id)
        )
        conn.commit()
        logger.info(f"Обновлен пользователь: {user_id}, {username}, {full_name}")
    except Exception as e:
        conn.rollback()
        logger.error(f"Ошибка создания пользователя: {e}")
    finally:
        conn.close()

def get_user_role(user_id: int):
    user = get_user(user_id)
    if user:
        return user[7] if len(user) > 7 else 'user'
    return 'user'

def set_user_role(user_id: int, role: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE users SET role = ? WHERE user_id = ?",
            (role, user_id)
        )
        conn.commit()
        logger.info(f"Пользователю {user_id} установлена роль: {role}")
    except Exception as e:
        conn.rollback()
        logger.error(f"Ошибка установки роли: {e}")
    finally:
        conn.close()

def get_user_by_id_or_username(identifier: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        user_id = int(identifier)
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()
        if user:
            conn.close()
            return user
    except ValueError:
        pass
    clean_identifier = identifier.lstrip('@')
    cursor.execute("SELECT * FROM users WHERE username = ?", (clean_identifier,))
    user = cursor.fetchone()
    conn.close()
    return user

def get_user_by_referral_code(code: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE referral_code = ?", (code.upper(),))
    user = cursor.fetchone()
    conn.close()
    return user

def set_referral_code(user_id: int, code: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE users SET referral_code = ? WHERE user_id = ?",
            (code.upper(), user_id)
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Ошибка установки реферального кода: {e}")
    finally:
        conn.close()

def add_referral(referrer_id: int, referred_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT referrer_id FROM users WHERE user_id = ?",
            (referred_id,)
        )
        result = cursor.fetchone()
        if result and result[0] is not None:
            conn.close()
            return False, "Пользователь уже является рефералом"
        cursor.execute(
            "SELECT username, full_name FROM users WHERE user_id = ?",
            (referred_id,)
        )
        referred_info = cursor.fetchone()
        referred_username = referred_info[0] if referred_info else "без юзернейма"
        referred_full_name = referred_info[1] if referred_info else "Неизвестно"
        cursor.execute(
            "UPDATE users SET referrer_id = ? WHERE user_id = ?",
            (referrer_id, referred_id)
        )
        cursor.execute(
            """INSERT INTO referral_logs (referrer_id, referred_id, referred_username, referred_full_name)
            VALUES (?, ?, ?, ?)""",
            (referrer_id, referred_id, referred_username, referred_full_name)
        )
        conn.commit()
        logger.info(f"Реферал добавлен: {referrer_id} -> {referred_id} ({referred_username})")
        return True, "OK"
    except Exception as e:
        conn.rollback()
        logger.error(f"Ошибка добавления реферала: {e}")
        return False, "Ошибка добавления"
    finally:
        conn.close()

def get_user_referrals(user_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """SELECT u.user_id, u.username, u.full_name, u.created_at 
           FROM users u
           WHERE u.referrer_id = ?
           ORDER BY u.created_at DESC""",
        (user_id,)
    )
    referrals = cursor.fetchall()
    conn.close()
    return referrals

def log_referral_click(referrer_id: int, referred_id: int, username: str, full_name: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """INSERT INTO referral_logs (referrer_id, referred_id, referred_username, referred_full_name)
            VALUES (?, ?, ?, ?)""",
            (referrer_id, referred_id, username, full_name)
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Ошибка логирования реферального клика: {e}")
    finally:
        conn.close()

# ========== ТИКЕТЫ ==========
def create_ticket(user_id: int, subject: str, text: str, topic_id: int = None, topic_name: str = None):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO tickets (user_id, subject, topic_id, topic_name) VALUES (?, ?, ?, ?)",
            (user_id, subject, topic_id, topic_name)
        )
        ticket_id = cursor.lastrowid
        cursor.execute(
            "INSERT INTO ticket_messages (ticket_id, user_id, message) VALUES (?, ?, ?)",
            (ticket_id, user_id, text)
        )
        conn.commit()
        logger.info(f"Создан тикет #{ticket_id} для пользователя {user_id}")
        return ticket_id
    except Exception as e:
        conn.rollback()
        logger.error(f"Ошибка создания тикета: {e}")
        return None
    finally:
        conn.close()

def update_ticket_topic(ticket_id: int, topic_id: int, topic_name: str = None):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if topic_name:
            cursor.execute(
                "UPDATE tickets SET topic_id = ?, topic_name = ? WHERE id = ?",
                (topic_id, topic_name, ticket_id)
            )
        else:
            cursor.execute(
                "UPDATE tickets SET topic_id = ? WHERE id = ?",
                (topic_id, ticket_id)
            )
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Ошибка обновления темы тикета: {e}")
    finally:
        conn.close()

def get_ticket(ticket_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
    ticket = cursor.fetchone()
    conn.close()
    return ticket

def get_ticket_by_topic_id(topic_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tickets WHERE topic_id = ?", (topic_id,))
    ticket = cursor.fetchone()
    conn.close()
    return ticket

def get_ticket_messages(ticket_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """SELECT tm.*, u.username 
           FROM ticket_messages tm
           LEFT JOIN users u ON tm.user_id = u.user_id
           WHERE tm.ticket_id = ?
           ORDER BY tm.created_at ASC""",
        (ticket_id,)
    )
    messages = cursor.fetchall()
    conn.close()
    return messages

def add_ticket_message(ticket_id: int, user_id: int, message: str, is_from_support: bool = False, media_type: str = None, file_id: str = None):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO ticket_messages (ticket_id, user_id, message, is_from_support, media_type, file_id) VALUES (?, ?, ?, ?, ?, ?)",
            (ticket_id, user_id, message, 1 if is_from_support else 0, media_type, file_id)
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Ошибка добавления сообщения в тикет: {e}")
    finally:
        conn.close()

def get_user_tickets(user_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """SELECT t.*, 
           (SELECT COUNT(*) FROM ticket_messages WHERE ticket_id = t.id) as message_count
           FROM tickets t
           WHERE t.user_id = ?
           ORDER BY t.created_at DESC""",
        (user_id,)
    )
    tickets = cursor.fetchall()
    conn.close()
    return tickets

def get_all_tickets(status: str = None):
    conn = get_db_connection()
    cursor = conn.cursor()
    if status:
        cursor.execute("SELECT * FROM tickets WHERE status = ? ORDER BY created_at DESC", (status,))
    else:
        cursor.execute("SELECT * FROM tickets ORDER BY created_at DESC")
    tickets = cursor.fetchall()
    conn.close()
    return tickets

def update_ticket_status(ticket_id: int, status: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if status == 'closed':
            cursor.execute(
                "UPDATE tickets SET status = ?, closed_at = CURRENT_TIMESTAMP WHERE id = ?",
                (status, ticket_id)
            )
        else:
            cursor.execute(
                "UPDATE tickets SET status = ? WHERE id = ?",
                (status, ticket_id)
            )
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Ошибка обновления статуса тикета: {e}")
    finally:
        conn.close()

def update_ticket_priority(ticket_id: int, priority: str) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE tickets SET priority = ? WHERE id = ?",
            (priority, ticket_id)
        )
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        logger.error(f"Ошибка обновления приоритета: {e}")
        return False
    finally:
        conn.close()

def assign_ticket(ticket_id: int, agent_id: int) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE tickets SET agent_id = ?, status = 'in_progress' WHERE id = ?",
            (agent_id, ticket_id)
        )
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        logger.error(f"Ошибка назначения тикета: {e}")
        return False
    finally:
        conn.close()

# ========== ОЦЕНКИ И СТАТИСТИКА АГЕНТОВ ==========
def rate_ticket(ticket_id: int, user_id: int, agent_id: int, rating: int, comment: str = None):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO ticket_ratings (ticket_id, user_id, agent_id, rating, comment) VALUES (?, ?, ?, ?, ?)",
            (ticket_id, user_id, agent_id, rating, comment)
        )
        cursor.execute(
            "UPDATE tickets SET rating = ?, rating_comment = ? WHERE id = ?",
            (rating, comment, ticket_id)
        )
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        logger.error(f"Ошибка сохранения оценки тикета: {e}")
        return False
    finally:
        conn.close()

def get_agent_stats(agent_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT COUNT(DISTINCT t.id) 
        FROM tickets t
        JOIN ticket_messages tm ON t.id = tm.ticket_id
        WHERE tm.user_id = ? AND tm.is_from_support = 1
    ''', (agent_id,))
    total_tickets = cursor.fetchone()[0]

    cursor.execute('''
        SELECT COUNT(*) FROM tickets 
        WHERE closed_by = ? AND status = 'closed'
    ''', (agent_id,))
    closed_tickets = cursor.fetchone()[0]

    cursor.execute('''
        SELECT AVG(rating), COUNT(*) FROM ticket_ratings WHERE agent_id = ?
    ''', (agent_id,))
    row = cursor.fetchone()
    avg_rating = row[0] or 0
    ratings_count = row[1] or 0

    cursor.execute('''
        SELECT rating, COUNT(*) FROM ticket_ratings WHERE agent_id = ? GROUP BY rating
    ''', (agent_id,))
    rating_dist = {r: c for r, c in cursor.fetchall()}

    conn.close()
    return {
        'total_tickets': total_tickets,
        'closed_tickets': closed_tickets,
        'avg_rating': round(avg_rating, 2),
        'ratings_count': ratings_count,
        'rating_dist': rating_dist
    }

def get_top_agents(limit: int = 10):
    """
    Возвращает список лучших агентов по среднему рейтингу.
    Каждый элемент кортежа: (username, full_name, avg_rating, votes)
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT u.username, u.full_name, AVG(tr.rating) as avg_rating, COUNT(tr.id) as votes
        FROM ticket_ratings tr
        JOIN users u ON tr.agent_id = u.user_id
        GROUP BY tr.agent_id
        ORDER BY avg_rating DESC, votes DESC
        LIMIT ?
    ''', (limit,))
    top = cursor.fetchall()
    conn.close()
    return top

# ========== ПРОМОКОДЫ ==========
def create_promocode(code: str, discount_percent: int, max_uses: int = 1, expires_at: datetime = None):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """INSERT INTO promocodes (code, discount_percent, max_uses, expires_at) 
            VALUES (?, ?, ?, ?)""",
            (code.upper(), discount_percent, max_uses, expires_at)
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Ошибка создания промокода: {e}")
    finally:
        conn.close()

def get_promocode(code: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM promocodes WHERE code = ?",
        (code.upper(),)
    )
    promocode = cursor.fetchone()
    conn.close()
    return promocode

def use_promocode(user_id: int, promocode_id: int, order_id: int = None):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT * FROM used_promocodes WHERE user_id = ? AND promocode_id = ?",
            (user_id, promocode_id)
        )
        if cursor.fetchone():
            conn.close()
            return False
        cursor.execute(
            "UPDATE promocodes SET used_count = used_count + 1 WHERE id = ? AND (max_uses = 0 OR used_count < max_uses)",
            (promocode_id,)
        )
        cursor.execute(
            "INSERT INTO used_promocodes (user_id, promocode_id, order_id) VALUES (?, ?, ?)",
            (user_id, promocode_id, order_id)
        )
        if order_id:
            cursor.execute(
                "SELECT discount_percent FROM promocodes WHERE id = ?",
                (promocode_id,)
            )
            discount_percent = cursor.fetchone()[0]
            cursor.execute(
                "UPDATE orders SET promocode_id = ?, discount = total_price * ? / 100 WHERE id = ?",
                (promocode_id, discount_percent, order_id)
            )
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        logger.error(f"Ошибка использования промокода: {e}")
        return False
    finally:
        conn.close()

def check_promocode_valid(code: str, user_id: int):
    promocode = get_promocode(code)
    if not promocode:
        return False, "Промокод не найден"
    promocode_id, code_text, discount_percent, max_uses, used_count, created_at, expires_at = promocode
    if expires_at:
        try:
            date_formats = [
                '%Y-%m-%d %H:%M:%S.%f',
                '%Y-%m-%d %H:%M:%S',
                '%Y-%m-%d %H:%M',
                '%Y-%m-%d'
            ]
            expires_at_datetime = None
            for date_format in date_formats:
                try:
                    expires_at_datetime = datetime.strptime(expires_at, date_format)
                    break
                except ValueError:
                    continue
            if expires_at_datetime and expires_at_datetime < datetime.now():
                return False, "Промокод истёк"
        except Exception as e:
            logger.error(f"Ошибка парсинга даты {expires_at}: {e}")
            return False, "Ошибка проверки срока действия промокода"
    if max_uses > 0 and used_count >= max_uses:
        return False, "Промокод уже использован максимальное количество раз"
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT * FROM used_promocodes WHERE user_id = ? AND promocode_id = ?",
            (user_id, promocode_id)
        )
        if cursor.fetchone():
            return False, "Вы уже использовали этот промокод"
    finally:
        conn.close()
    return True, discount_percent

def get_all_promocodes():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM promocodes ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return rows

def delete_promocode(promocode_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM promocodes WHERE id = ?", (promocode_id,))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Ошибка удаления промокода: {e}")
        return False
    finally:
        conn.close()

def update_promocode(promocode_id: int, discount: int, max_uses: int, expires_at: datetime = None):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE promocodes SET discount_percent = ?, max_uses = ?, expires_at = ? WHERE id = ?",
            (discount, max_uses, expires_at, promocode_id)
        )
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Ошибка обновления промокода: {e}")
        return False
    finally:
        conn.close()

def get_active_promocodes():
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute("""
        SELECT * FROM promocodes 
        WHERE (expires_at IS NULL OR expires_at > ?) 
        AND (max_uses = 0 OR used_count < max_uses)
        ORDER BY created_at DESC
    """, (now,))
    rows = cursor.fetchall()
    conn.close()
    return rows

# ========== ЗАКАЗЫ ==========
def create_order(user_id: int, amount: int, recipient_username: str, screenshot_path: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        total_price = amount * get_star_rate()
        cursor.execute(
            """INSERT INTO orders 
            (user_id, amount, recipient_username, screenshot_path, total_price) 
            VALUES (?, ?, ?, ?, ?)""",
            (user_id, amount, recipient_username, screenshot_path, total_price)
        )
        order_id = cursor.lastrowid
        conn.commit()
        return order_id
    except Exception as e:
        conn.rollback()
        logger.error(f"Ошибка создания заказа: {e}")
        return None
    finally:
        conn.close()

def get_order_status(order_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT status FROM orders WHERE id = ?",
        (order_id,)
    )
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def update_order_status(order_id: int, status: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE orders SET status = ? WHERE id = ?",
            (status, order_id)
        )
        if status == 'approved':
            cursor.execute(
                "SELECT user_id, amount, total_price, discount FROM orders WHERE id = ?",
                (order_id,)
            )
            order = cursor.fetchone()
            if order:
                user_id, amount, total_price, discount = order
                final_price = total_price - (discount or 0)
                cursor.execute(
                    """INSERT INTO purchase_history 
                    (user_id, order_id, amount, total_price) 
                    VALUES (?, ?, ?, ?)""",
                    (user_id, order_id, amount, final_price)
                )
                cursor.execute(
                    "UPDATE users SET total_spent = total_spent + ? WHERE user_id = ?",
                    (final_price, user_id)
                )
                user = get_user(user_id)
                if user and user[9]:
                    create_referral_reward(user[9], user_id, order_id, final_price)
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Ошибка обновления статуса заказа: {e}")
    finally:
        conn.close()

def get_user_orders(user_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """SELECT o.id, o.amount, o.total_price - o.discount as final_price, o.status, o.created_at, 
           h.purchase_date 
           FROM orders o
           LEFT JOIN purchase_history h ON o.id = h.order_id
           WHERE o.user_id = ?
           ORDER BY o.created_at DESC""",
        (user_id,)
    )
    orders = cursor.fetchall()
    conn.close()
    return orders

def get_pending_orders():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """SELECT o.*, u.username as buyer_username 
           FROM orders o
           JOIN users u ON o.user_id = u.user_id
           WHERE o.status = 'pending'
           ORDER BY o.created_at ASC"""
    )
    orders = cursor.fetchall()
    conn.close()
    return orders

def cancel_order(order_id: int, user_id: int, reason: str) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE orders 
            SET status = 'canceled', 
                canceled_reason = ?,
                canceled_at = CURRENT_TIMESTAMP 
            WHERE id = ? AND user_id = ? AND status = 'pending'
        """, (reason, order_id, user_id))
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        conn.rollback()
        logger.error(f"Ошибка отмены заказа: {e}")
        return False
    finally:
        conn.close()

def add_order_comment(order_id: int, user_id: int, comment: str) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE orders SET comment = ? WHERE id = ? AND user_id = ?",
            (comment, order_id, user_id)
        )
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        conn.rollback()
        logger.error(f"Ошибка добавления комментария: {e}")
        return False
    finally:
        conn.close()

# ========== ВЫВОДЫ ==========
def create_withdrawal(user_id: int, amount: int, screenshot_path: str, recipient_username: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT 1 FROM withdrawals WHERE user_id = ? AND status = 'pending'",
            (user_id,)
        )
        if cursor.fetchone():
            conn.close()
            return None, "У вас уже есть активная заявка"
        payout_amount = int(amount * (1 - get_withdraw_commission()))
        withdrawal_id = str(uuid.uuid4())
        cursor.execute(
            """INSERT INTO withdrawals (withdrawal_id, user_id, amount, payout_amount, 
            screenshot_path, recipient_username) 
            VALUES (?, ?, ?, ?, ?, ?)""",
            (withdrawal_id, user_id, amount, payout_amount, screenshot_path, recipient_username)
        )
        conn.commit()
        return withdrawal_id, "OK"
    except Exception as e:
        conn.rollback()
        logger.error(f"Ошибка создания заявки на вывод: {e}")
        return None, "Ошибка создания заявки"
    finally:
        conn.close()

def get_pending_withdrawals():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """SELECT w.*, u.username, u.user_id as buyer_id 
        FROM withdrawals w
        JOIN users u ON w.user_id = u.user_id
        WHERE w.status = 'pending'
        ORDER BY w.created_at ASC"""
    )
    withdrawals = cursor.fetchall()
    conn.close()
    return withdrawals

def update_withdrawal_status(withdrawal_id: str, status: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE withdrawals SET status = ?, processed_at = CURRENT_TIMESTAMP WHERE withdrawal_id = ?",
            (status, withdrawal_id)
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Ошибка обновления статуса вывода: {e}")
    finally:
        conn.close()

# ========== ОБМЕН ==========
def create_exchange(user_id: int, from_currency: str, to_currency: str, amount: int, recipient_username: str = None):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if from_currency == 'real' and to_currency == 'virtual':
            converted = int(amount * get_real_to_virtual_rate() * (1 - get_exchange_commission()))
            commission = int(amount * get_real_to_virtual_rate() * get_exchange_commission())
            status = 'pending'
        else:
            converted = int(amount * get_virtual_to_real_rate() * (1 - get_virtual_to_real_commission()))
            commission = int(amount * get_virtual_to_real_rate() * get_virtual_to_real_commission())
            status = 'pending'
        exchange_id = str(uuid.uuid4())
        cursor.execute(
            """INSERT INTO exchanges 
               (exchange_id, user_id, from_currency, to_currency, amount, 
                converted_amount, commission, recipient_username, status) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (exchange_id, user_id, from_currency, to_currency, amount, 
             converted, commission, recipient_username, status)
        )
        conn.commit()
        return exchange_id, converted, commission
    except Exception as e:
        conn.rollback()
        logger.error(f"Ошибка создания обмена: {e}")
        return None, 0, 0
    finally:
        conn.close()

def get_exchange(exchange_id: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM exchanges WHERE exchange_id = ?", (exchange_id,))
    row = cursor.fetchone()
    conn.close()
    return row

def update_exchange_status(exchange_id: str, status: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE exchanges SET status = ? WHERE exchange_id = ?",
            (status, exchange_id)
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Ошибка обновления статуса обмена: {e}")
    finally:
        conn.close()

# ========== ИГРЫ ==========
def create_game_record(game_id: str, user_id: int, game_type: str, bet_amount: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """INSERT INTO games (game_id, user_id, game_type, bet_amount, processed) 
            VALUES (?, ?, ?, ?, 0)""",
            (game_id, user_id, game_type, bet_amount)
        )
        game_record_id = cursor.lastrowid
        conn.commit()
        return game_record_id
    except Exception as e:
        conn.rollback()
        logger.error(f"Ошибка создания записи игры: {e}")
        return None
    finally:
        conn.close()

def update_game_result(game_id: str, win_amount: int, result: str, dice_message_id: int = None):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if dice_message_id:
            cursor.execute(
                """UPDATE games SET win_amount = ?, result = ?, dice_message_id = ?, processed = 1 
                WHERE game_id = ?""",
                (win_amount, result, dice_message_id, game_id)
            )
        else:
            cursor.execute(
                """UPDATE games SET win_amount = ?, result = ?, processed = 1 
                WHERE game_id = ?""",
                (win_amount, result, game_id)
            )
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Ошибка обновления результата игры: {e}")
    finally:
        conn.close()

def check_game_processed(game_id: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT processed FROM games WHERE game_id = ?",
            (game_id,)
        )
        result = cursor.fetchone()
        return result[0] if result else 0
    except:
        return 0
    finally:
        conn.close()

# ========== РЕФЕРАЛЬНЫЕ НАГРАДЫ ==========
def create_referral_reward(referrer_id: int, referred_id: int, purchase_id: int, amount: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT 1 FROM referral_rewards WHERE referred_id = ? AND purchase_id = ?",
            (referred_id, purchase_id)
        )
        if cursor.fetchone():
            conn.close()
            return False
        reward_amount = int(amount * get_referral_levels()[0]['percent'] / 100)  # упрощённо
        cursor.execute(
            """INSERT INTO referral_rewards (referrer_id, referred_id, purchase_id, amount, currency) 
            VALUES (?, ?, ?, ?, ?)""",
            (referrer_id, referred_id, purchase_id, reward_amount, REFERRAL_REWARD_TYPE)
        )
        if REFERRAL_REWARD_TYPE == 'virtual':
            update_balance(referrer_id, reward_amount, 'virtual', 'add')
        else:
            update_balance(referrer_id, reward_amount, 'real', 'add')
        cursor.execute(
            "UPDATE referral_rewards SET paid = 1 WHERE id = ?",
            (cursor.lastrowid,)
        )
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        logger.error(f"Ошибка создания реферального вознаграждения: {e}")
        return False
    finally:
        conn.close()

def get_referral_stats(user_id: int) -> dict:
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM users WHERE referrer_id = ?", (user_id,))
    total_refs = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(DISTINCT u.user_id)
        FROM users u
        JOIN purchase_history ph ON u.user_id = ph.user_id
        WHERE u.referrer_id = ?
    """, (user_id,))
    active_refs = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COALESCE(SUM(ph.total_price), 0)
        FROM users u
        JOIN purchase_history ph ON u.user_id = ph.user_id
        WHERE u.referrer_id = ?
    """, (user_id,))
    total_volume = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COALESCE(SUM(amount), 0)
        FROM referral_rewards
        WHERE referrer_id = ? AND paid = 1
    """, (user_id,))
    earned = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COALESCE(SUM(amount), 0)
        FROM referral_rewards
        WHERE referrer_id = ? AND paid = 0
    """, (user_id,))
    pending = cursor.fetchone()[0]

    level = get_referral_level(total_refs)

    conn.close()
    return {
        "total": total_refs,
        "active": active_refs,
        "volume": total_volume,
        "earned": earned,
        "pending": pending,
        "level": level
    }

# ========== БАНЫ И ВАРНЫ ==========
def add_warn(user_id: int, reason: str, moderator_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO warns (user_id, reason, moderator_id) VALUES (?, ?, ?)",
            (user_id, reason, moderator_id)
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Ошибка добавления предупреждения: {e}")
    finally:
        conn.close()

def get_warns(user_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM warns WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,)
    )
    warns = cursor.fetchall()
    conn.close()
    return warns

def remove_warn(warn_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM warns WHERE id = ?", (warn_id,))
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Ошибка удаления предупреждения: {e}")
    finally:
        conn.close()

def add_ban(user_id: int, reason: str, moderator_id: int, banned_until=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM bans WHERE user_id = ?", (user_id,))
        cursor.execute(
            "INSERT INTO bans (user_id, reason, moderator_id, banned_until) VALUES (?, ?, ?, ?)",
            (user_id, reason, moderator_id, banned_until)
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Ошибка добавления бана: {e}")
    finally:
        conn.close()

def remove_ban(user_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM bans WHERE user_id = ?", (user_id,))
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Ошибка удаления бана: {e}")
    finally:
        conn.close()

def get_ban(user_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM bans WHERE user_id = ?", (user_id,))
    ban = cursor.fetchone()
    conn.close()
    return ban

def is_user_banned(user_id: int) -> bool:
    ban = get_ban(user_id)
    if not ban:
        return False
    banned_until = ban[4]
    if banned_until:
        try:
            date_formats = [
                '%Y-%m-%d %H:%M:%S.%f',
                '%Y-%m-%d %H:%M:%S',
                '%Y-%m-%d %H:%M',
                '%Y-%m-%d'
            ]
            banned_until_datetime = None
            for date_format in date_formats:
                try:
                    banned_until_datetime = datetime.strptime(banned_until, date_format)
                    break
                except ValueError:
                    continue
            if banned_until_datetime and banned_until_datetime < datetime.now():
                remove_ban(user_id)
                return False
        except Exception as e:
            logger.error(f"Ошибка парсинга даты бана {banned_until}: {e}")
    return True

def get_all_bans():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM bans ORDER BY banned_at DESC")
    bans = cursor.fetchall()
    conn.close()
    return bans

# ========== ЗАМОРОЗКА ==========
def freeze_user(user_id: int, reason: str, admin_id: int = None) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT OR REPLACE INTO freezes (user_id, reason, frozen_by) VALUES (?, ?, ?)",
            (user_id, reason, admin_id)
        )
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Ошибка заморозки: {e}")
        return False
    finally:
        conn.close()

def unfreeze_user(user_id: int) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM freezes WHERE user_id = ?", (user_id,))
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Ошибка разморозки: {e}")
        return False
    finally:
        conn.close()

def is_user_frozen(user_id: int) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM freezes WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def get_freeze_info(user_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT reason, frozen_at FROM freezes WHERE user_id = ?",
        (user_id,)
    )
    result = cursor.fetchone()
    conn.close()
    return result if result else None

def get_all_frozen_users():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT f.user_id, u.username, u.full_name, f.reason, f.frozen_at
        FROM freezes f
        LEFT JOIN users u ON f.user_id = u.user_id
        ORDER BY f.frozen_at DESC
    ''')
    rows = cursor.fetchall()
    conn.close()
    return rows

# ========== АДМИН-ЛОГИ ==========
def log_admin_action(admin_id: int, action_type: str, target_type: str = None, target_id: int = None, details: dict = None):
    from helpers import get_user_role
    role = get_user_role(admin_id)
    if role in ['owner', 'tech_admin']:
        return
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT username FROM users WHERE user_id = ?", (admin_id,)
        )
        row = cursor.fetchone()
        admin_username = row[0] if row else None
        cursor.execute(
            """INSERT INTO admin_logs 
               (admin_id, admin_username, action_type, target_type, target_id, details) 
               VALUES (?, ?, ?, ?, ?, ?)""",
            (admin_id, admin_username, action_type, target_type, target_id,
             json.dumps(details, ensure_ascii=False) if details else None)
        )
        conn.commit()
    except Exception as e:
        logger.error(f"Ошибка логирования: {e}")
    finally:
        conn.close()

def get_admin_logs(admin_id: int = None, action_type: str = None, days: int = 7, limit: int = 50):
    conn = get_db_connection()
    cursor = conn.cursor()
    query = "SELECT * FROM admin_logs WHERE created_at >= datetime('now', ?)"
    params = [f'-{days} days']
    if admin_id:
        query += " AND admin_id = ?"
        params.append(admin_id)
    if action_type:
        query += " AND action_type = ?"
        params.append(action_type)
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return rows

# ========== НАСТРОЙКИ ==========
_settings_cache = {}

def get_setting(key: str, default=None):
    if key in _settings_cache:
        return _settings_cache[key]
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    value = row[0] if row else default
    _settings_cache[key] = value
    return value

def set_setting(key: str, value: str):
    global _settings_cache
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
            (key, value)
        )
        conn.commit()
        _settings_cache[key] = value
        return True
    except Exception as e:
        logger.error(f"Ошибка установки настройки {key}: {e}")
        return False
    finally:
        conn.close()

def clear_settings_cache():
    global _settings_cache
    _settings_cache = {}

def get_star_rate():
    return float(get_setting('star_rate', str(STAR_RATE)))

def get_min_stars():
    return int(get_setting('min_stars', str(MIN_STARS)))

def get_withdraw_commission():
    return float(get_setting('withdraw_commission', str(WITHDRAW_COMMISSION)))

def get_exchange_commission():
    return float(get_setting('exchange_commission', str(EXCHANGE_COMMISSION)))

def get_withdraw_min_real():
    return int(get_setting('withdraw_min_real', str(WITHDRAW_MIN_REAL)))

def get_real_to_virtual_rate():
    return float(get_setting('real_to_virtual_rate', str(REAL_TO_VIRTUAL_RATE)))

def get_virtual_to_real_rate():
    return float(get_setting('virtual_to_real_rate', str(VIRTUAL_TO_REAL_RATE)))

def get_real_to_virtual_min():
    return int(get_setting('real_to_virtual_min', str(REAL_TO_VIRTUAL_MIN)))

def get_virtual_to_real_commission():
    return float(get_setting('virtual_to_real_commission', str(VIRTUAL_TO_REAL_COMMISSION)))

def is_rounding_enabled():
    return get_setting('rounding_enabled', '1') == '1'

def get_referral_levels():
    levels_json = get_setting('referral_levels', '[]')
    try:
        return json.loads(levels_json)
    except:
        return [
            {"min": 0, "max": 5, "percent": 5, "name": "Бронзовый"},
            {"min": 5, "max": 20, "percent": 7, "name": "Серебряный"},
            {"min": 20, "max": 999999, "percent": 10, "name": "Золотой"}
        ]

def get_referral_level(referrals_count: int):
    levels = get_referral_levels()
    for level in levels:
        if level["min"] <= referrals_count < level["max"]:
            return level
    return levels[0]

def set_maintenance_mode(enabled: bool, reason: str = None, duration_minutes: int = None):
    set_setting('maintenance_mode', '1' if enabled else '0')
    if reason:
        set_setting('maintenance_reason', reason)
    if enabled and duration_minutes:
        until = datetime.now() + timedelta(minutes=duration_minutes)
        set_setting('maintenance_until', until.strftime('%Y-%m-%d %H:%M:%S'))
    else:
        set_setting('maintenance_until', '')

def is_maintenance_mode() -> bool:
    return get_setting('maintenance_mode', '0') == '1'

def get_maintenance_info() -> dict:
    reason = get_setting('maintenance_reason', 'Плановые работы')
    until_str = get_setting('maintenance_until', '')
    remaining = "не определено"
    if until_str:
        try:
            until = datetime.strptime(until_str, '%Y-%m-%d %H:%M:%S')
            now = datetime.now()
            if until > now:
                delta = until - now
                total_seconds = int(delta.total_seconds())
                if total_seconds < 60:
                    remaining = f"{total_seconds} сек"
                elif total_seconds < 3600:
                    remaining = f"{total_seconds // 60} мин"
                elif total_seconds < 86400:
                    remaining = f"{total_seconds // 3600} час"
                else:
                    remaining = f"{total_seconds // 86400} дн"
            else:
                remaining = "истекло"
        except:
            remaining = "ошибка"
    return {
        'reason': reason,
        'remaining': remaining,
        'until': until_str
    }

# ========== ДОСТИЖЕНИЯ ==========
def get_user_achievements(user_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT al.code, al.name, al.description, al.icon, ua.earned_at
        FROM user_achievements ua
        JOIN achievements_list al ON ua.ach_code = al.code
        WHERE ua.user_id = ?
        ORDER BY ua.earned_at DESC
    ''', (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def award_achievement(user_id: int, ach_code: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT OR IGNORE INTO user_achievements (user_id, ach_code) VALUES (?, ?)",
            (user_id, ach_code)
        )
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Ошибка выдачи ачивки: {e}")
        return False
    finally:
        conn.close()

def remove_achievement_from_user(user_id: int, ach_code: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "DELETE FROM user_achievements WHERE user_id = ? AND ach_code = ?",
            (user_id, ach_code)
        )
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Ошибка удаления ачивки: {e}")
        return False
    finally:
        conn.close()

def get_all_achievements():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM achievements_list ORDER BY created_at")
    rows = cursor.fetchall()
    conn.close()
    return rows

def create_achievement(code: str, name: str, description: str, icon: str = '🏆', hidden: bool = False):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO achievements_list (code, name, description, icon, hidden) VALUES (?, ?, ?, ?, ?)",
            (code, name, description, icon, 1 if hidden else 0)
        )
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Ошибка создания ачивки: {e}")
        return False
    finally:
        conn.close()

def delete_achievement(code: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM achievements_list WHERE code = ?", (code,))
        cursor.execute("DELETE FROM user_achievements WHERE ach_code = ?", (code,))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Ошибка удаления ачивки: {e}")
        return False
    finally:
        conn.close()

def update_achievement(code: str, name: str, description: str, icon: str, hidden: bool):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE achievements_list SET name = ?, description = ?, icon = ?, hidden = ? WHERE code = ?",
            (name, description, icon, 1 if hidden else 0, code)
        )
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Ошибка обновления ачивки: {e}")
        return False
    finally:
        conn.close()

def get_achievement_stats(code: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM user_achievements WHERE ach_code = ?", (code,))
    count = cursor.fetchone()[0]
    conn.close()
    return count

# ========== ССЫЛКИ СО СКИДКОЙ ==========
def create_discount_link(discount_percent: int, max_uses: int = 1, expires_at: datetime = None, comment: str = "", created_by: int = None):
    code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO discount_links (code, discount_percent, max_uses, expires_at, comment, created_by) VALUES (?, ?, ?, ?, ?, ?)",
            (code, discount_percent, max_uses, expires_at, comment, created_by)
        )
        conn.commit()
        return code
    except Exception as e:
        logger.error(f"Ошибка создания ссылки-скидки: {e}")
        return None
    finally:
        conn.close()

def get_discount_link(code: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM discount_links WHERE code = ?", (code,))
    link = cursor.fetchone()
    conn.close()
    return link

def use_discount_link(code: str, user_id: int):
    link = get_discount_link(code)
    if not link:
        return None, "Ссылка не найдена"
    link_id, code, discount, max_uses, used_count, expires_at, comment, created_by, created_at = link
    if expires_at:
        try:
            exp_date = datetime.strptime(expires_at, '%Y-%m-%d %H:%M:%S')
            if exp_date < datetime.now():
                return None, "Ссылка истекла"
        except:
            pass
    if max_uses > 0 and used_count >= max_uses:
        return None, "Лимит использований исчерпан"
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE discount_links SET used_count = used_count + 1 WHERE code = ?",
            (code,)
        )
        cursor.execute(
            "INSERT INTO user_discounts (user_id, discount_percent, source_link, expires_at) VALUES (?, ?, ?, ?)",
            (user_id, discount, code, expires_at)
        )
        conn.commit()
        return discount, "OK"
    except Exception as e:
        conn.rollback()
        logger.error(f"Ошибка применения ссылки-скидки: {e}")
        return None, "Ошибка активации"
    finally:
        conn.close()

def get_user_active_discount(user_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT discount_percent, expires_at FROM user_discounts
        WHERE user_id = ? AND used = 0
        ORDER BY created_at DESC LIMIT 1
    ''', (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        discount, expires = row
        if expires:
            try:
                exp_date = datetime.strptime(expires, '%Y-%m-%d %H:%M:%S')
                if exp_date < datetime.now():
                    return None
            except:
                pass
        return discount
    return None

def mark_discount_used(user_id: int, order_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            UPDATE user_discounts SET used = 1, applied_to_order_id = ?
            WHERE user_id = ? AND used = 0
        ''', (order_id, user_id))
        conn.commit()
    except Exception as e:
        logger.error(f"Ошибка отметки скидки использованной: {e}")
    finally:
        conn.close()

def get_all_discount_links():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM discount_links ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return rows

def delete_discount_link(code: str) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM discount_links WHERE code = ?", (code,))
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Ошибка удаления ссылки-скидки: {e}")
        return False
    finally:
        conn.close()

# ========== ОТЗЫВЫ ==========
def create_feedback(user_id: int, order_id: int, rating: int, text: str = None, photo_id: str = None):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO feedback (user_id, order_id, rating, text, photo_id) VALUES (?, ?, ?, ?, ?)",
            (user_id, order_id, rating, text, photo_id)
        )
        conn.commit()
        return cursor.lastrowid
    except Exception as e:
        logger.error(f"Ошибка создания отзыва: {e}")
        return None
    finally:
        conn.close()

def get_order_feedback(order_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM feedback WHERE order_id = ?", (order_id,))
    row = cursor.fetchone()
    conn.close()
    return row

def update_feedback_status(feedback_id: int, status: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE feedback SET status = ? WHERE id = ?",
            (status, feedback_id)
        )
        conn.commit()
    except Exception as e:
        logger.error(f"Ошибка обновления статуса отзыва: {e}")
    finally:
        conn.close()

# ========== ТОП ПОКУПАТЕЛЕЙ ==========
def get_top_buyers(limit: int = 10):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """SELECT u.username, u.full_name, 
                  SUM(h.total_price) as total_spent,
                  COUNT(h.id) as orders_count
           FROM purchase_history h
           JOIN users u ON h.user_id = u.user_id
           GROUP BY h.user_id
           ORDER BY total_spent DESC
           LIMIT ?""",
        (limit,)
    )
    top_buyers = cursor.fetchall()
    conn.close()
    return top_buyers

def get_top_buyers_no_admins(limit: int = 10):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT u.username, u.full_name, SUM(h.total_price) as total_spent
        FROM purchase_history h
        JOIN users u ON h.user_id = u.user_id
        WHERE u.role NOT IN ('admin', 'tech_admin', 'owner', 'moder', 'agent')
        GROUP BY h.user_id
        ORDER BY total_spent DESC
        LIMIT ?
    ''', (limit,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_cached_top_buyers(limit: int = 10):
    # кэширование реализовано в helpers.py через aiocache
    return get_top_buyers_no_admins(limit)

def invalidate_top_cache():
    cache_delete("top_buyers")

# ========== СТАТИСТИКА ==========
def get_revenue_for_period(days: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """SELECT COALESCE(SUM(total_price), 0) 
           FROM purchase_history 
           WHERE purchase_date >= datetime('now', ?)""",
        (f'-{days} days',)
    )
    revenue = cursor.fetchone()[0]
    conn.close()
    return revenue

def get_active_users_count(days: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """SELECT COUNT(DISTINCT user_id) 
           FROM purchase_history 
           WHERE purchase_date >= datetime('now', ?)""",
        (f'-{days} days',)
    )
    count = cursor.fetchone()[0]
    conn.close()
    return count

def get_average_check(days: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """SELECT COALESCE(AVG(total_price), 0) 
           FROM purchase_history 
           WHERE purchase_date >= datetime('now', ?)""",
        (f'-{days} days',)
    )
    avg = cursor.fetchone()[0]
    conn.close()
    return avg

def get_sales_by_day(days: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """SELECT DATE(purchase_date) as day, 
                  COUNT(*) as orders_count,
                  SUM(total_price) as revenue
           FROM purchase_history 
           WHERE purchase_date >= datetime('now', ?)
           GROUP BY DATE(purchase_date)
           ORDER BY day DESC""",
        (f'-{days} days',)
    )
    sales = cursor.fetchall()
    conn.close()
    return sales

def count_users_by_role():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT role, COUNT(*) FROM users GROUP BY role")
    rows = cursor.fetchall()
    conn.close()
    return dict(rows)

def get_users_by_activity(days: int = 7):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT user_id, username, full_name, last_action 
        FROM users 
        WHERE last_action >= datetime('now', ?)
        ORDER BY last_action DESC
    ''', (f'-{days} days',))
    active = cursor.fetchall()
    cursor.execute('''
        SELECT user_id, username, full_name, last_action 
        FROM users 
        WHERE last_action < datetime('now', ?) OR last_action IS NULL
        ORDER BY last_action DESC
    ''', (f'-{days} days',))
    inactive = cursor.fetchall()
    conn.close()
    return active, inactive

def get_all_users():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username, full_name FROM users")
    users = cursor.fetchall()
    conn.close()
    return users

# ========== БАЛАНС ==========
def update_balance(user_id: int, amount: int, currency: str = 'real', operation: str = 'add'):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if currency == 'real':
            cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        else:
            cursor.execute("SELECT virtual_balance FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        if not result:
            conn.close()
            return False
        current_balance = result[0]
        if operation == 'subtract' and current_balance < amount:
            conn.close()
            return False
        if currency == 'real':
            if operation == 'add':
                cursor.execute(
                    "UPDATE users SET balance = balance + ? WHERE user_id = ?",
                    (amount, user_id)
                )
            else:
                cursor.execute(
                    "UPDATE users SET balance = balance - ? WHERE user_id = ?",
                    (amount, user_id)
                )
        else:
            if operation == 'add':
                cursor.execute(
                    "UPDATE users SET virtual_balance = virtual_balance + ? WHERE user_id = ?",
                    (amount, user_id)
                )
            else:
                cursor.execute(
                    "UPDATE users SET virtual_balance = virtual_balance - ? WHERE user_id = ?",
                    (amount, user_id)
                )
        cursor.execute(
            "UPDATE users SET last_action = CURRENT_TIMESTAMP WHERE user_id = ?",
            (user_id,)
        )
        conn.commit()
        invalidate_balance_cache(user_id)
        return True
    except Exception as e:
        conn.rollback()
        logger.error(f"Ошибка обновления баланса: {e}")
        return False
    finally:
        conn.close()

def invalidate_balance_cache(user_id: int):
    cache_delete(f"balance:{user_id}")

# ========== ПРОВЕРКА ДЕЙСТВИЙ ==========
def check_action_allowed(user_id: int, action_type: str, action_id: str = None):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if action_id:
            cursor.execute(
                "SELECT 1 FROM processed_actions WHERE action_id = ?",
                (action_id,)
            )
            if cursor.fetchone():
                conn.close()
                return False, "Действие уже обработано"
        cursor.execute(
            "SELECT last_action FROM users WHERE user_id = ?",
            (user_id,)
        )
        result = cursor.fetchone()
        if result and result[0]:
            try:
                last_action = datetime.strptime(result[0], '%Y-%m-%d %H:%M:%S')
                if (datetime.now() - last_action).seconds < ACTION_TIMEOUT_SECONDS:
                    conn.close()
                    return False, f"Слишком быстро! Подождите {ACTION_TIMEOUT_SECONDS} секунд"
            except:
                pass
        conn.close()
        return True, "OK"
    except Exception as e:
        conn.close()
        logger.error(f"Ошибка проверки действия: {e}")
        return False, "Ошибка проверки"

def mark_action_processed(action_id: str, user_id: int, action_type: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT OR IGNORE INTO processed_actions (action_id, user_id, action_type) VALUES (?, ?, ?)",
            (action_id, user_id, action_type)
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Ошибка отметки действия: {e}")
    finally:
        conn.close()

# ========== ШАБЛОНЫ ТИКЕТОВ ==========
def save_ticket_template(name: str, text: str):
    set_setting(f'ticket_template_{name}', text)

def get_ticket_template(name: str):
    return get_setting(f'ticket_template_{name}', '')

def delete_ticket_template(name: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM settings WHERE key = ?", (f'ticket_template_{name}',))
        conn.commit()
    except Exception as e:
        logger.error(f"Ошибка удаления шаблона: {e}")
    finally:
        conn.close()

def get_all_ticket_templates():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM settings WHERE key LIKE 'ticket_template_%'")
    rows = cursor.fetchall()
    conn.close()
    templates = {}
    for key, value in rows:
        name = key.replace('ticket_template_', '')
        templates[name] = value
    return templates

# ========== ДЕНЬ РОЖДЕНИЯ БОТА ==========
def get_birthday_info():
    return {
        'date': get_setting('birthday_date', ''),
        'enabled': get_setting('birthday_enabled', '0') == '1',
        'text': get_setting('birthday_text', ''),
        'photo': get_setting('birthday_photo', ''),
        'audio': get_setting('birthday_audio', ''),
        'sticker': get_setting('birthday_sticker', ''),
        'mode': get_setting('birthday_mode', 'random')
    }

def set_birthday_info(data: dict):
    for key, value in data.items():
        set_setting(f'birthday_{key}', str(value) if value is not None else '')

# ========== АКЦИИ ==========
def create_sale(name: str, discount_type: str, discount_value: int, start_date: datetime, end_date: datetime):
    sales = get_setting('sales', '[]')
    try:
        sales_list = json.loads(sales)
    except:
        sales_list = []
    sale_id = len(sales_list) + 1
    sale = {
        'id': sale_id,
        'name': name,
        'type': discount_type,
        'value': discount_value,
        'start': start_date.isoformat(),
        'end': end_date.isoformat(),
        'active': True
    }
    sales_list.append(sale)
    set_setting('sales', json.dumps(sales_list))
    return sale_id

def get_all_sales():
    sales = get_setting('sales', '[]')
    try:
        return json.loads(sales)
    except:
        return []

def update_sale(sale_id: int, data: dict):
    sales = get_setting('sales', '[]')
    try:
        sales_list = json.loads(sales)
        for sale in sales_list:
            if sale['id'] == sale_id:
                sale.update(data)
                break
        set_setting('sales', json.dumps(sales_list))
        return True
    except:
        return False

def delete_sale(sale_id: int):
    sales = get_setting('sales', '[]')
    try:
        sales_list = json.loads(sales)
        sales_list = [s for s in sales_list if s['id'] != sale_id]
        set_setting('sales', json.dumps(sales_list))
        return True
    except:
        return False

# ========== БЕКАПЫ ==========
def create_backup():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = f"{BACKUP_DIR}/backup_{timestamp}.db"
    shutil.copy2(DATABASE_NAME, backup_file)
    return backup_file

def list_backups():
    files = glob.glob(f"{BACKUP_DIR}/backup_*.db")
    files.sort(key=os.path.getmtime, reverse=True)
    backups = []
    for f in files:
        size = os.path.getsize(f)
        mtime = os.path.getmtime(f)
        backups.append({
            'path': f,
            'name': os.path.basename(f),
            'size': size,
            'mtime': datetime.fromtimestamp(mtime)
        })
    return backups

def restore_backup(filepath: str):
    try:
        shutil.copy2(filepath, DATABASE_NAME)
        clear_settings_cache()
        return True
    except Exception as e:
        logger.error(f"Ошибка восстановления бекапа: {e}")
        return False

def cleanup_old_backups(keep_count: int = 7):
    files = glob.glob(f"{BACKUP_DIR}/backup_*.db")
    files.sort(key=os.path.getmtime)
    if len(files) > keep_count:
        for f in files[:-keep_count]:
            os.remove(f)

# ========== РАССЫЛКИ ==========
def create_mailing(
    admin_id: int,
    filter_type: str,
    text: str = None,
    media_file_id: str = None,
    media_type: str = None,
    button_text: str = None,
    button_url: str = None,
    scheduled_at: datetime = None
) -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO mailings 
            (admin_id, filter_type, text, media_file_id, media_type, button_text, button_url, scheduled_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (admin_id, filter_type, text, media_file_id, media_type, button_text, button_url, scheduled_at))
        conn.commit()
        return cursor.lastrowid
    except Exception as e:
        logger.error(f"Ошибка создания рассылки: {e}")
        return None
    finally:
        conn.close()

def get_pending_mailings():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM mailings 
        WHERE status = 'pending' 
        AND (scheduled_at IS NULL OR scheduled_at <= CURRENT_TIMESTAMP)
        ORDER BY created_at ASC
    """)
    rows = cursor.fetchall()
    conn.close()
    return rows

def update_mailing_status(mailing_id: int, status: str, sent: int = 0, failed: int = 0):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE mailings 
            SET status = ?, sent_count = sent_count + ?, fail_count = fail_count + ?
            WHERE id = ?
        """, (status, sent, failed, mailing_id))
        conn.commit()
    except Exception as e:
        logger.error(f"Ошибка обновления статуса рассылки: {e}")
    finally:
        conn.close()

def get_mailing_stats(mailing_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM mailings WHERE id = ?", (mailing_id,))
    row = cursor.fetchone()
    conn.close()
    return row

# ========== ВЕРСИЯ БД ==========
def get_db_version():
    return "3.0"