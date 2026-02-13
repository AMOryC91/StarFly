#// FILE: bot/handlers/errors.py
import logging
from aiogram import Router, types
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

logger = logging.getLogger(__name__)

router = Router(name="errors")

@router.errors()
async def errors_handler(event: types.ErrorEvent):
    """Глобальный обработчик ошибок."""
    logger.error(f"Ошибка: {event.exception}", exc_info=event.exception)
    
    try:
        # Игнорируем ошибку "message is not modified"
        if isinstance(event.exception, TelegramBadRequest):
            if "message is not modified" in str(event.exception).lower():
                return
        
        # Если ошибка возникла при обработке callback'а – уведомляем пользователя
        if isinstance(event.update, types.CallbackQuery):
            await event.update.callback_query.answer(
                "⚠️ Произошла ошибка. Попробуйте позже.",
                show_alert=True
            )
    except:
        pass