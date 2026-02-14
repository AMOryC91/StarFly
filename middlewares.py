# FILE: middlewares.py
import logging
from datetime import datetime
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery

from database import is_user_banned, get_ban, is_user_frozen, get_freeze_info, is_maintenance_mode, get_maintenance_info
from helpers import has_access, format_datetime  # <-- ИСПРАВЛЕНО

logger = logging.getLogger(__name__)

# ========== МИДЛВАРЬ ПРОВЕРКИ БАНА ==========
class CheckBanMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message | CallbackQuery, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        # Пропускаем команду /start и /support
        if isinstance(event, Message):
            if event.text and event.text.startswith(('/start', '/support')):
                return await handler(event, data)
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id
        else:
            return await handler(event, data)

        if is_user_banned(user_id):
            ban = get_ban(user_id)
            reason = ban[2] if ban and len(ban) > 2 else "Не указана"
            banned_until = ban[4] if ban and len(ban) > 4 else None
            
            if isinstance(event, Message):
                ban_text = "🚫 ВЫ ЗАБАНЕНЫ!\n\n"
                ban_text += f"Причина: {reason}\n"
                if banned_until:
                    try:
                        ban_until_str = format_datetime(banned_until)
                        ban_text += f"Истекает: {ban_until_str}"
                    except:
                        ban_text += f"Истекает: {banned_until}"
                else:
                    ban_text += "Навсегда"
                await event.answer(ban_text)
                return
            elif isinstance(event, CallbackQuery):
                await event.answer("🚫 Вы забанены и не можете использовать бота!", show_alert=True)
                return

        return await handler(event, data)


# ========== МИДЛВАРЬ ПРОВЕРКИ ЗАМОРОЗКИ ==========
class CheckFreezeMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message | CallbackQuery, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        # Пропускаем команду /start и /support
        if isinstance(event, Message):
            if event.text and event.text.startswith(('/start', '/support')):
                return await handler(event, data)
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id
        else:
            return await handler(event, data)

        if is_user_frozen(user_id):
            freeze_info = get_freeze_info(user_id)
            reason = freeze_info[0] if freeze_info else "Не указана"
            date = freeze_info[1] if freeze_info else "Неизвестно"
            text = (
                f"❄️ ВАШ АККАУНТ ЗАМОРОЖЕН\n\n"
                f"Причина: {reason}\n"
                f"Дата: {format_datetime(date)}\n\n"
                f"Для разморозки обратитесь в поддержку: /support"
            )
            if isinstance(event, Message):
                await event.answer(text)
            else:
                await event.answer("❌ Ваш аккаунт заморожен", show_alert=True)
                await event.message.answer(text)
            return

        return await handler(event, data)


# ========== МИДЛВАРЬ ПРОВЕРКИ ТЕХНИЧЕСКИХ РАБОТ ==========
class CheckMaintenanceMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message | CallbackQuery, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        if not is_maintenance_mode():
            return await handler(event, data)

        if isinstance(event, Message):
            user_id = event.from_user.id
            # Админы и тех.админы пропускаются
            if has_access(user_id, 'tech_admin'):
                return await handler(event, data)
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id
            if has_access(user_id, 'tech_admin'):
                return await handler(event, data)

        info = get_maintenance_info()
        text = (
            "🔧 <b>Ведутся технические работы</b>\n\n"
            f"📋 Причина: {info['reason']}\n"
            f"⏳ Ориентировочно: {info['duration']}\n\n"
            "Приносим извинения за неудобства!\n"
            "Попробуйте зайти позже."
        )

        if isinstance(event, Message):
            await event.answer(text)
        elif isinstance(event, CallbackQuery):
            await event.answer("🔧 Технические работы", show_alert=True)
            await event.message.answer(text)

        return


# ========== ЭКСПОРТ ЭКЗЕМПЛЯРОВ ==========
check_ban_middleware = CheckBanMiddleware()
check_freeze_middleware = CheckFreezeMiddleware()
check_maintenance_middleware = CheckMaintenanceMiddleware()
