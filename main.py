# FILE: main.py
import logging
import asyncio
from datetime import datetime

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties

from config import BOT_TOKEN, OWNER_ID, TECH_ADMIN_ID
from database import init_db, get_user, create_user, set_user_role

from handlers.admin import router as admin_router
from handlers.tickets import router as tickets_router
from handlers.profile import router as profile_router
from handlers.shop import router as shop_router
from handlers.games import router as games_router
from handlers.errors import router as errors_router

from middlewares import (
    check_ban_middleware,
    check_freeze_middleware,
    check_maintenance_middleware
)

from helpers import cleanup_old_screenshots  # <-- импортируем функцию очистки

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация БД
init_db()

# Создание бота и диспетчера
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
bot.start_time = datetime.now()

dp = Dispatcher(storage=MemoryStorage())

# ===== ОБНОВЛЕНИЕ ПРОФИЛЕЙ АДМИНИСТРАТОРОВ =====
async def update_admin_profiles():
    try:
        owner_chat = await bot.get_chat(OWNER_ID)
        owner_username = owner_chat.username or ""
        owner_full_name = owner_chat.full_name or f"User {OWNER_ID}"
        owner = get_user(OWNER_ID)
        if not owner:
            create_user(OWNER_ID, owner_username, owner_full_name)
        set_user_role(OWNER_ID, 'owner')
        logger.info(f"Профиль владельца обновлён: @{owner_username} (роль: owner)")

        tech_chat = await bot.get_chat(TECH_ADMIN_ID)
        tech_username = tech_chat.username or ""
        tech_full_name = tech_chat.full_name or f"User {TECH_ADMIN_ID}"
        tech = get_user(TECH_ADMIN_ID)
        if not tech:
            create_user(TECH_ADMIN_ID, tech_username, tech_full_name)
        set_user_role(TECH_ADMIN_ID, 'tech_admin')
        logger.info(f"Профиль тех. администратора обновлён: @{tech_username} (роль: tech_admin)")
    except Exception as e:
        logger.error(f"Ошибка при обновлении профилей администраторов: {e}")

# ===== ФОНОВАЯ ЗАДАЧА ДЛЯ ОЧИСТКИ СКРИНШОТОВ =====
async def scheduled_cleanup():
    """Запускается раз в сутки и удаляет скриншоты старше 30 дней."""
    while True:
        await asyncio.sleep(86400)  # 24 часа
        try:
            deleted = cleanup_old_screenshots(days=30)
            logger.info(f"Очистка скриншотов: удалено {deleted} файлов")
        except Exception as e:
            logger.error(f"Ошибка при очистке скриншотов: {e}")

# ===== РЕГИСТРАЦИЯ MIDDLEWARE =====
dp.message.middleware(check_ban_middleware)
dp.callback_query.middleware(check_ban_middleware)
dp.message.middleware(check_maintenance_middleware)
dp.callback_query.middleware(check_maintenance_middleware)
dp.message.middleware(check_freeze_middleware)
dp.callback_query.middleware(check_freeze_middleware)

# ===== ПОДКЛЮЧЕНИЕ РОУТЕРОВ =====
dp.include_router(admin_router)
dp.include_router(tickets_router)
dp.include_router(profile_router)
dp.include_router(shop_router)
dp.include_router(games_router)
dp.include_router(errors_router)

async def main():
    await update_admin_profiles()
    asyncio.create_task(scheduled_cleanup())  # <-- запускаем фоновую задачу
    logger.info("Бот запущен")
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
