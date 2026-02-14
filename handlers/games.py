#// FILE: bot/handlers/games.py
import logging
import random
import uuid
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import (
    MINES_GAME_WIN_REWARD, MINES_GAME_LOSE_PENALTY,
    CASINO_BET_AMOUNTS, CASINO_WIN_CHANCE, CASINO_WIN_MULTIPLIER
)
from database import (
    get_user, update_balance, create_game_record, update_game_result,
    check_game_processed, check_action_allowed, mark_action_processed
)
from keyboards import MenuCallback, GameCallback, get_games_menu, get_mines_game_keyboard, get_casino_bet_amount_keyboard, get_back_to_menu_keyboard
from states import GameStates
from helpers import is_duplicate_action

logger = logging.getLogger(__name__)

router = Router(name="games")

# ========== МЕНЮ ИГР ==========
@router.callback_query(MenuCallback.filter(F.action == "games"))
async def show_games_menu(callback: types.CallbackQuery):
    games_text = (
        "🎰 <b>Мини-игры</b>\n\n"
        "Выберите игру:\n\n"
        "🎯 <b>Мины</b>\n"
        "• Выберите 1 из 3 шаров\n"
        "• 1 шар выигрышный\n"
        f"• Победа: +{MINES_GAME_WIN_REWARD} ⭐\n"
        f"• Проигрыш: -{MINES_GAME_LOSE_PENALTY} ⭐\n\n"
        "🎰 <b>Казино</b>\n"
        f"• Ставки: {', '.join(map(str, CASINO_BET_AMOUNTS))} ⭐\n"
        "• Выигрыш только при 777\n"
        f"• Шанс выигрыша: {CASINO_WIN_CHANCE*100}%\n"
        f"• Выигрыш: {CASINO_WIN_MULTIPLIER}x от ставки"
    )
    await callback.message.edit_text(games_text, reply_markup=get_games_menu())
    await callback.answer()

# ========== ИГРА "МИНЫ" ==========
@router.callback_query(MenuCallback.filter(F.action == "game_mines"))
async def start_mines_game(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    user = get_user(user_id)

    # Проверка баланса
    if user[5] < MINES_GAME_LOSE_PENALTY:
        await callback.answer(
            f"❌ Недостаточно виртуальных звёзд! Нужно минимум {MINES_GAME_LOSE_PENALTY} ⭐",
            show_alert=True
        )
        return

    # Дедупликация
    action_id = f"mines_start_{user_id}_{uuid.uuid4()}"
    allowed, msg = check_action_allowed(user_id, "mines_start", action_id)
    if not allowed:
        await callback.answer(msg, show_alert=True)
        return

    game_id = str(uuid.uuid4())
    create_game_record(game_id, user_id, "mines", 0)

    winning_ball = random.randint(1, 3)
    await state.update_data(game_id=game_id, winning_ball=winning_ball)

    await callback.message.edit_text(
        "🎯 <b>Игра «Мины»</b>\n\n"
        "Выберите один из трёх шаров. Один из них выигрышный!\n"
        f"Победа: +{MINES_GAME_WIN_REWARD} ⭐\n"
        f"Проигрыш: -{MINES_GAME_LOSE_PENALTY} ⭐",
        reply_markup=get_mines_game_keyboard(game_id)
    )
    mark_action_processed(action_id, user_id, "mines_start")
    await callback.answer()

@router.callback_query(GameCallback.filter(F.action == "mines_choice"))
async def process_mines_choice(callback: types.CallbackQuery, callback_data: GameCallback, state: FSMContext):
    user_id = callback.from_user.id
    game_id = callback_data.game_id
    choice = callback_data.choice

    if check_game_processed(game_id):
        await callback.answer("Эта игра уже обработана!", show_alert=True)
        return

    data = await state.get_data()
    if data.get('game_id') != game_id:
        await callback.answer("Игра не найдена!", show_alert=True)
        return

    winning_ball = data['winning_ball']

    if choice == winning_ball:
        if update_balance(user_id, MINES_GAME_WIN_REWARD, 'virtual', 'add'):
            update_game_result(game_id, MINES_GAME_WIN_REWARD, "win")
            result_text = (
                f"🎉 <b>Поздравляем! Вы выиграли!</b>\n\n"
                f"Вы выбрали шар {choice} — это выигрышный шар!\n"
                f"На ваш виртуальный баланс начислено: +{MINES_GAME_WIN_REWARD} ⭐"
            )
        else:
            result_text = "❌ Ошибка начисления приза"
    else:
        if update_balance(user_id, MINES_GAME_LOSE_PENALTY, 'virtual', 'subtract'):
            update_game_result(game_id, 0, "lose")
            result_text = (
                f"😢 <b>Вы проиграли</b>\n\n"
                f"Вы выбрали шар {choice}\n"
                f"Выигрышный шар был: {winning_ball}\n"
                f"С вашего виртуального баланса списано: -{MINES_GAME_LOSE_PENALTY} ⭐"
            )
        else:
            result_text = "❌ Недостаточно виртуальных звёзд для игры"

    await callback.message.edit_text(result_text, reply_markup=get_back_to_menu_keyboard())
    await state.clear()
    await callback.answer()

# ========== КАЗИНО ==========
@router.callback_query(MenuCallback.filter(F.action == "game_casino"))
async def start_casino_game(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "🎰 <b>Казино (только виртуальные звёзды)</b>\n\n"
        "Выберите сумму ставки:",
        reply_markup=get_casino_bet_amount_keyboard()
    )
    await callback.answer()

@router.callback_query(GameCallback.filter(F.action == "casino_bet"))
async def process_casino_bet(callback: types.CallbackQuery, callback_data: GameCallback, state: FSMContext):
    from main import bot

    user_id = callback.from_user.id
    bet_amount = callback_data.bet_amount

    user = get_user(user_id)
    if user[5] < bet_amount:
        await callback.answer("❌ Недостаточно виртуальных звёзд!", show_alert=True)
        return

    # Дедупликация
    action_id = f"casino_bet_{user_id}_{uuid.uuid4()}"
    if await is_duplicate_action(action_id):
        await callback.answer("⏳ Игра уже запущена", show_alert=True)
        return

    game_id = str(uuid.uuid4())
    create_game_record(game_id, user_id, "casino_virtual", bet_amount)

    if not update_balance(user_id, bet_amount, 'virtual', 'subtract'):
        await callback.answer("❌ Ошибка списания!", show_alert=True)
        return

    dice_message = await bot.send_dice(chat_id=user_id, emoji="🎰")
    await state.update_data(
        game_id=game_id,
        dice_message_id=dice_message.message_id,
        bet_amount=bet_amount
    )
    await callback.message.edit_text(
        f"🎰 <b>Крутим барабаны...</b>\n\nСтавка: {bet_amount} ⭐",
        reply_markup=None
    )
    await callback.answer()

@router.message(F.dice.emoji == "🎰")
async def process_casino_dice(message: types.Message, state: FSMContext):
    from main import bot

    data = await state.get_data()
    if not data or 'game_id' not in data:
        return

    game_id = data['game_id']
    dice_message_id = message.message_id

    if data.get('dice_message_id') != dice_message_id:
        return

    if check_game_processed(game_id):
        return

    dice_value = message.dice.value
    result = "win" if dice_value == 777 else "lose"
    bet_amount = data['bet_amount']

    if result == "win":
        win_amount = int(bet_amount * CASINO_WIN_MULTIPLIER)
        update_balance(message.from_user.id, win_amount, 'virtual', 'add')
    else:
        win_amount = 0

    update_game_result(game_id, win_amount, result, dice_message_id)

    if result == "win":
        result_text = (
            f"🎉 <b>ДЖЕКПОТ! 777!</b>\n\n"
            f"Ваша ставка: {bet_amount} ⭐\n"
            f"Выигрыш: {win_amount} ⭐\n"
            f"Множитель: {CASINO_WIN_MULTIPLIER}x"
        )
    else:
        result_text = (
            f"😢 <b>Вы проиграли</b>\n\n"
            f"Ваша ставка: {bet_amount} ⭐\n"
            f"С вашего баланса списано: {bet_amount} ⭐"
        )

    try:
        await bot.send_message(message.chat.id, result_text, reply_markup=get_back_to_menu_keyboard())
    except Exception as e:
        logger.error(f"Ошибка отправки результата казино: {e}")

    await state.clear()
