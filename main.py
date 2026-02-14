# FILE: main.py
import logging
import asyncio
from datetime import datetime

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties

from config import BOT_TOKEN, OWNER_ID, TECH_ADMIN_ID
from database import init_db, get_db_connection, get_user, create_user, set_user_role

# Импортируем роутеры из всех хендлеров
from handlers.admin import router as admin_router
from handlers.tickets import router as tickets_router
from handlers.profile import router as profile_router
from handlers.shop import router as shop_router
from handlers.games import router as games_router
from handlers.utils import router as utils_router
from handlers.errors import router as errors_router

 Импортируем мидлвари
from middlewares import (
    check_ban_middleware,
    check_freeze_middleware,
    check_maintenance_middleware
)

# Импортируем все CallbackData для использования в фильтрах (если необходимо где-то в main)
# (но они не нужны, если мы используем роутеры; оставим для совместимости)
from keyboards import (
    MenuCallback, OrderCallback, TicketCallback, SubjectCallback,
    GameCallback, WithdrawalCallback, ExchangeCallback, StarsPurchaseCallback,
    AdminCallback, PromocodeCallback, DiscountLinkCallback, UserCallback,
    AchievementCallback, MailingCallback, BackupCallback, SettingsCallback,
    FeedbackCallback, TemplateCallback
)

# Импортируем состояния (необязательно, но может пригодиться)
from states import *

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация БД
init_db()

# Создание бота и диспетчера
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher(storage=MemoryStorage())

# Сохраняем время запуска для uptime
bot.start_time = datetime.now()

# ===== ОБНОВЛЕНИЕ ПРОФИЛЕЙ АДМИНИСТРАТОРОВ =====
async def update_admin_profiles():
    """Обновляет информацию о владельце и тех. администраторе в БД из Telegram."""
    try:
        # Владелец
        owner_chat = await bot.get_chat(OWNER_ID)
        owner_username = owner_chat.username or ""
        owner_full_name = owner_chat.full_name or f"User {OWNER_ID}"
        
        owner = get_user(OWNER_ID)
        if not owner:
            create_user(OWNER_ID, owner_username, owner_full_name)
        # Принудительно устанавливаем роль owner
        set_user_role(OWNER_ID, 'owner')
        logger.info(f"Профиль владельца обновлён: @{owner_username} (роль: owner)")
        
        # Технический администратор
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
dp.include_router(utils_router)
dp.include_router(errors_router)

async def main():
    await update_admin_profiles()
    logger.info("Бот запущен")
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
