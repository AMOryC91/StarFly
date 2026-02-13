# FILE: states.py
from aiogram.fsm.state import State, StatesGroup

class PurchaseStates(StatesGroup):
    waiting_for_amount = State()
    waiting_for_username = State()
    waiting_for_promocode = State()
    waiting_for_screenshot = State()
    waiting_cancel_reason = State()
    waiting_comment = State()
    waiting_recipient = State()
    waiting_amount = State()
    waiting_promo = State()
    waiting_screenshot = State()
    waiting_cancel = State()
    waiting_feedback_text = State()
    waiting_feedback_photo = State()

class CalculatorStates(StatesGroup):
    waiting_for_stars = State()
    waiting_for_rubles = State()
    waiting_stars = State()
    waiting_rubles = State()

class TicketStates(StatesGroup):
    waiting_for_subject = State()
    waiting_for_message = State()
    waiting_for_reply = State()
    waiting_subject = State()
    waiting_ticket_message = State()
    waiting_reply = State()

class GameStates(StatesGroup):
    waiting_for_mines_choice = State()
    waiting_mines = State()
    waiting_casino_bet = State()

class ExchangeStates(StatesGroup):
    waiting_for_exchange_type = State()
    waiting_for_exchange_amount = State()
    waiting_for_recipient = State()
    waiting_for_screenshot = State()
    waiting_exchange_type = State()
    waiting_exchange_amount = State()
    waiting_exchange_recipient = State()
    waiting_exchange_screenshot = State()

class WithdrawalStates(StatesGroup):
    waiting_for_withdrawal_amount = State()
    waiting_for_recipient = State()
    waiting_withdrawal_amount = State()
    waiting_withdrawal_recipient = State()

class AdminStates(StatesGroup):
    # ========== ЭКОНОМИКА ==========
    waiting_star_rate = State()
    waiting_for_rate = State()
    waiting_rate = State()
    waiting_set_rate = State()
    waiting_edit_rate = State()
    
    waiting_withdraw_commission = State()
    waiting_for_commission = State()
    waiting_commission = State()
    waiting_withdraw_comm = State()
    waiting_set_withdraw_commission = State()
    waiting_edit_withdraw_commission = State()
    
    waiting_exchange_commission_real = State()
    waiting_exchange_commission_virtual = State()
    waiting_exchange_commission = State()
    waiting_set_exchange_commission = State()
    
    waiting_min_stars = State()
    waiting_for_min_stars = State()
    waiting_min_purchase = State()
    waiting_set_min_stars = State()
    waiting_edit_min_stars = State()
    
    waiting_min_withdraw = State()
    waiting_for_min_withdraw = State()
    waiting_withdraw_min = State()
    waiting_set_min_withdraw = State()
    waiting_edit_min_withdraw = State()
    
    waiting_rounding = State()
    waiting_toggle_rounding = State()
    waiting_set_rounding = State()
    
    waiting_economy_value = State()
    waiting_economy_key = State()
    
    # ========== ПРОМОКОДЫ ==========
    waiting_promocode_code = State()
    waiting_for_promocode_code = State()
    waiting_promo_code = State()
    waiting_promocode = State()
    waiting_code = State()
    
    waiting_promocode_discount = State()
    waiting_for_promocode_discount = State()
    waiting_promo_discount = State()
    waiting_discount = State()
    
    waiting_promocode_max_uses = State()
    waiting_for_promocode_max_uses = State()
    waiting_promo_max_uses = State()
    waiting_promocode_uses = State()
    waiting_promo_uses = State()
    waiting_max_uses = State()
    
    waiting_promocode_expires = State()
    waiting_for_promocode_expires = State()
    waiting_promo_expires = State()
    waiting_expires = State()
    waiting_expires_at = State()
    
    waiting_promocode_id = State()
    waiting_promo_id = State()
    waiting_edit_promocode_id = State()
    
    waiting_promocode_edit_field = State()
    waiting_promocode_new_value = State()
    
    # ========== ПОЛЬЗОВАТЕЛИ ==========
    waiting_user_id = State()
    waiting_for_user_id = State()
    waiting_userid = State()
    waiting_target_user = State()
    waiting_username = State()
    waiting_user = State()
    
    waiting_give_amount = State()
    waiting_for_give_amount = State()
    waiting_give_stars = State()
    waiting_give = State()
    waiting_amount_to_give = State()
    waiting_give_stars_amount = State()
    
    waiting_take_amount = State()
    waiting_for_take_amount = State()
    waiting_take_stars = State()
    waiting_take = State()
    waiting_amount_to_take = State()
    waiting_deduct_stars_amount = State()
    
    waiting_freeze_reason = State()
    waiting_for_freeze_reason = State()
    waiting_freeze = State()
    waiting_freeze_reason_text = State()
    waiting_freeze_reason_custom = State()
    
    waiting_user_role = State()
    waiting_for_user_role = State()
    waiting_role = State()
    waiting_new_role = State()
    waiting_change_role = State()
    
    waiting_user_search_query = State()
    waiting_user_action = State()
    waiting_user_search = State()
    
    # ========== АЧИВКИ ==========
    waiting_achievement_code = State()
    waiting_for_achievement_code = State()
    waiting_ach_code = State()
    waiting_achievement = State()
    
    waiting_achievement_name = State()
    waiting_for_achievement_name = State()
    waiting_ach_name = State()
    waiting_ach_name_input = State()  # синоним
    
    waiting_achievement_desc = State()
    waiting_for_achievement_desc = State()
    waiting_ach_desc = State()
    waiting_description = State()
    waiting_ach_description = State()  # <-- ДОБАВЛЕНО
    waiting_ach_description_input = State()  # синоним
    
    waiting_achievement_icon = State()
    waiting_for_achievement_icon = State()
    waiting_ach_icon = State()
    waiting_icon = State()
    
    waiting_achievement_id = State()
    waiting_ach_id = State()
    
    waiting_achievement_edit_field = State()
    waiting_achievement_new_value = State()
    
    waiting_achievement_user = State()
    waiting_achievement_code_to_award = State()
    waiting_achievement_code_to_remove = State()
    
    waiting_ach_user = State()
    waiting_ach_select = State()
    waiting_ach_hidden = State()
    waiting_ach_hidden_input = State()
    
    # ========== РАССЫЛКА ==========
    waiting_mailing_text = State()
    waiting_for_mailing_text = State()
    waiting_mail_text = State()
    waiting_mailing_message = State()
    
    waiting_mailing_media = State()
    waiting_for_mailing_media = State()
    waiting_mail_media = State()
    waiting_mailing_media_id = State()
    
    waiting_mailing_button = State()
    waiting_for_mailing_button = State()
    waiting_mail_button = State()
    waiting_mailing_button_text = State()
    
    waiting_mailing_button_url = State()
    waiting_for_mailing_button_url = State()
    waiting_mail_url = State()
    waiting_mailing_button_link = State()
    
    waiting_mailing_filter = State()
    waiting_mailing_filter_type = State()
    waiting_mailing_target = State()
    
    waiting_mailing_preview = State()
    waiting_mailing_confirm = State()
    
    waiting_mailing_id = State()
    waiting_mailing_schedule = State()
    
    # ========== АКЦИИ ==========
    waiting_sale_name = State()
    waiting_for_sale_name = State()
    waiting_promotion_name = State()
    
    waiting_sale_type = State()
    waiting_for_sale_type = State()
    waiting_promotion_type = State()
    
    waiting_sale_value = State()
    waiting_for_sale_value = State()
    waiting_promotion_value = State()
    
    waiting_sale_start = State()
    waiting_for_sale_start = State()
    waiting_promotion_start = State()
    
    waiting_sale_end = State()
    waiting_for_sale_end = State()
    waiting_promotion_end = State()
    
    waiting_sale_id = State()
    waiting_promotion_id = State()
    
    waiting_sale_edit_field = State()
    waiting_sale_new_value = State()
    
    # ========== ШАБЛОНЫ ТИКЕТОВ ==========
    waiting_template_name = State()
    waiting_for_template_name = State()
    waiting_template_title = State()
    
    waiting_template_content = State()
    waiting_for_template_content = State()
    waiting_template_text = State()
    waiting_template_message = State()
    
    waiting_template_id = State()
    
    waiting_template_edit_field = State()
    waiting_template_new_value = State()
    
    # ========== ДЕНЬ РОЖДЕНИЯ БОТА ==========
    waiting_birthday_text = State()
    waiting_for_birthday_text = State()
    waiting_birthday_message = State()
    
    waiting_birthday_media = State()
    waiting_for_birthday_media = State()
    
    waiting_birthday_photo = State()
    waiting_birthday_video = State()
    waiting_birthday_animation = State()
    waiting_birthday_audio = State()
    waiting_birthday_voice = State()
    waiting_birthday_sticker = State()
    waiting_birthday_document = State()
    
    waiting_birthday_date = State()
    waiting_birthday_mode = State()
    waiting_birthday_enabled = State()
    
    waiting_birthday_edit_field = State()
    waiting_birthday_new_value = State()
    
    # ========== БЕКАПЫ ==========
    waiting_backup_filename = State()
    waiting_for_backup_filename = State()
    waiting_restore_file = State()
    waiting_backup_action = State()
    waiting_restore_confirm = State()
    
    # ========== ТЕХНИЧЕСКИЕ РАБОТЫ ==========
    waiting_maintenance_reason = State()
    waiting_maintenance_duration = State()
    waiting_maintenance_action = State()
    waiting_maintenance_duration_unit = State()
    
    # ========== РЕДАКТИРОВАНИЕ ==========
    waiting_edit_promocode = State()
    waiting_edit_sale = State()
    waiting_edit_achievement = State()
    waiting_edit_template = State()
    waiting_edit_birthday = State()
    waiting_edit_user = State()
    waiting_edit_settings = State()
    waiting_edit_economy = State()
    
    waiting_edit_id = State()
    waiting_edit_field = State()
    waiting_edit_value = State()
    
    # ========== НАСТРОЙКИ ==========
    waiting_settings_key = State()
    waiting_settings_value = State()
    
    # ========== ЛОГИ ==========
    waiting_logs_filter_admin = State()
    waiting_logs_filter_action = State()
    waiting_logs_filter_date_from = State()
    waiting_logs_filter_date_to = State()
    
    # ========== ОБЩИЕ / УНИВЕРСАЛЬНЫЕ ==========
    waiting_input = State()
    waiting_confirm = State()
    waiting_value = State()
    waiting_reason = State()
    waiting_comment = State()
    waiting_description = State()
    waiting_name = State()
    waiting_code = State()
    waiting_discount = State()
    waiting_expires = State()
    waiting_uses = State()
    waiting_amount = State()
    waiting_percent = State()
    waiting_text = State()
    waiting_data = State()
    waiting_id = State()
    waiting_key = State()
    waiting_number = State()
    waiting_string = State()
    waiting_boolean = State()
    waiting_date = State()
    waiting_time = State()
    waiting_datetime = State()
    
    waiting_generic_text = State()
    waiting_generic_number = State()
    
    # ========== СПЕЦИАЛЬНЫЕ ДЛЯ АДМИНКИ ==========
    waiting_promo_edit = State()
    waiting_sale_edit = State()
    waiting_ach_edit = State()
    waiting_template_edit = State()
    waiting_birthday_edit = State()
    waiting_user_edit = State()
    
    # ========== ДЛЯ ОБРАБОТКИ НЕДОСТАЮЩИХ СОСТОЯНИЙ ==========
    waiting_ach_description_input = State()
    waiting_ach_icon_input = State()
    waiting_ach_hidden_input = State()
    waiting_ach_user_input = State()
    
    # ========== ДОПОЛНИТЕЛЬНЫЕ ==========
    waiting_promo_code_input = State()
    waiting_promo_discount_input = State()
    waiting_promo_max_uses_input = State()
    waiting_promo_expires_input = State()
    
    waiting_user_search_input = State()
    waiting_user_search_query_input = State()
    
    waiting_freeze_reason_input = State()
    
    waiting_mailing_text_input = State()
    waiting_mailing_media_input = State()
    waiting_mailing_button_text_input = State()
    waiting_mailing_button_url_input = State()
    
    waiting_sale_name_input = State()
    waiting_sale_type_input = State()
    waiting_sale_value_input = State()
    waiting_sale_start_input = State()
    waiting_sale_end_input = State()
    
    waiting_template_name_input = State()
    waiting_template_content_input = State()
    
    waiting_birthday_text_input = State()
    waiting_birthday_date_input = State()
    waiting_birthday_mode_input = State()
    
    waiting_maintenance_reason_input = State()
    waiting_maintenance_duration_input = State()
    
    waiting_restore_confirm_input = State()