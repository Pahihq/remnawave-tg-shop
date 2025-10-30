"""
Phone Transfer User Handlers - Isolated Module
This module contains all phone transfer payment user handlers to minimize conflicts with upstream updates.
"""
import logging
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from typing import Optional, Dict
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from aiogram import Bot

from config.settings import Settings
from bot.services.phone_transfer_service import PhoneTransferService
from bot.middlewares.i18n import JsonI18n
from bot.keyboards.inline.user_keyboards import (
    get_phone_transfer_receipt_keyboard,
    get_phone_transfer_pending_keyboard,
    get_back_to_main_menu_markup
)

router = Router(name="user_phone_transfer_router")

# Temporary session storage for receipt uploads (user_id -> {payment_id, timestamp})
_receipt_upload_sessions: Dict[int, Dict] = {}


@router.callback_query(F.data.startswith("pay_phone_transfer:"))
async def pay_phone_transfer_callback_handler(
        callback: types.CallbackQuery, settings: Settings, i18n_data: dict,
        session: AsyncSession, phone_transfer_service: PhoneTransferService):
    current_lang = i18n_data.get("current_language", settings.DEFAULT_LANGUAGE)
    i18n: Optional[JsonI18n] = i18n_data.get("i18n_instance")

    get_text = lambda key, **kwargs: i18n.gettext(current_lang, key, **kwargs) if i18n else key

    if not i18n or not callback.message:
        await callback.answer(get_text("error_occurred_try_again"), show_alert=True)
        return

    if not phone_transfer_service.is_configured():
        await callback.answer(get_text("payment_service_unavailable"), show_alert=True)
        return

    try:
        _, data_payload = callback.data.split(":", 1)
        months_str, price_str = data_payload.split(":")
        months = int(months_str)
        price_rub = float(price_str)
    except (ValueError, IndexError):
        logging.error(f"Invalid pay_phone_transfer data in callback: {callback.data}")
        await callback.answer(get_text("error_try_again"), show_alert=True)
        return

    user_id = callback.from_user.id
    payment_description = get_text("payment_description_subscription", months=months)

    # Create phone transfer payment request
    payment = await phone_transfer_service.create_payment_request(
        session, user_id, months, price_rub, "RUB", payment_description
    )
    
    if not payment:
        await callback.message.edit_text(get_text("error_payment_gateway"))
        await callback.answer(get_text("error_try_again"), show_alert=True)
        return

    # Get transfer instructions
    instructions = phone_transfer_service.get_transfer_instructions(price_rub, "RUB", months)
    
    # Create keyboard for receipt upload
    reply_markup = get_phone_transfer_receipt_keyboard(payment.payment_id, current_lang, i18n)
    
    try:
        await callback.message.edit_text(instructions, reply_markup=reply_markup, parse_mode="HTML")
    except Exception as e_edit:
        logging.warning(f"Edit message for phone transfer failed: {e_edit}. Sending new one.")
        await callback.message.answer(instructions, reply_markup=reply_markup, parse_mode="HTML")
    
    await callback.answer()


@router.callback_query(F.data.startswith("upload_receipt:"))
async def upload_receipt_callback_handler(
        callback: types.CallbackQuery, i18n_data: dict):
    current_lang = i18n_data.get("current_language", "ru")
    i18n: Optional[JsonI18n] = i18n_data.get("i18n_instance")

    get_text = lambda key, **kwargs: i18n.gettext(current_lang, key, **kwargs) if i18n else key

    if not i18n or not callback.message:
        await callback.answer(get_text("error_occurred_try_again"), show_alert=True)
        return

    try:
        payment_id = int(callback.data.split(":")[-1])
    except (ValueError, IndexError):
        logging.error(f"Invalid upload_receipt data in callback: {callback.data}")
        await callback.answer(get_text("error_try_again"), show_alert=True)
        return

    # Store payment_id in temporary session for this user
    user_id = callback.from_user.id
    _receipt_upload_sessions[user_id] = {
        'payment_id': payment_id,
        'timestamp': datetime.now()
    }
    
    # Send instruction message
    await callback.message.edit_text(
        get_text("upload_receipt_instruction", default="📸 Пожалуйста, отправьте фото или скриншот чека о переводе."),
        reply_markup=get_back_to_main_menu_markup(current_lang, i18n)
    )
    
    await callback.answer()


@router.message(F.photo)
async def handle_receipt_photo(
        message: types.Message, i18n_data: dict, session: AsyncSession,
        phone_transfer_service: PhoneTransferService):
    """Handle receipt photo upload for phone transfer payments"""
    current_lang = i18n_data.get("current_language", "ru")
    i18n: Optional[JsonI18n] = i18n_data.get("i18n_instance")

    get_text = lambda key, **kwargs: i18n.gettext(current_lang, key, **kwargs) if i18n else key

    # Check if this is a receipt upload by looking for active session
    user_id = message.from_user.id
    session_data = _receipt_upload_sessions.get(user_id)
    
    if not session_data:
        return  # No active receipt upload session
    
    # Check if session is not expired (5 minutes)
    if (datetime.now() - session_data['timestamp']).total_seconds() > 300:
        del _receipt_upload_sessions[user_id]
        return  # Session expired
    
    payment_id = session_data['payment_id']
    
    # Get the largest photo size
    photo = message.photo[-1]
    
    # Upload receipt
    success = await phone_transfer_service.upload_receipt(
        session, payment_id, str(photo.file_id), photo.file_id
    )
    
    if success:
        # Clear the session
        del _receipt_upload_sessions[user_id]
        
        # Send confirmation to user
        await message.answer(
            get_text("receipt_uploaded_success", default="✅ Чек успешно загружен! Ваш платеж отправлен на проверку администратору. Вы получите уведомление после подтверждения."),
            reply_markup=get_phone_transfer_pending_keyboard(current_lang, i18n)
        )
        
        # Notify admins about new receipt
        await notify_admins_about_receipt(message.bot, payment_id, message.from_user, photo.file_id)
    else:
        await message.answer(
            get_text("receipt_upload_failed", default="❌ Не удалось загрузить чек. Пожалуйста, попробуйте еще раз или обратитесь в поддержку."),
            reply_markup=get_back_to_main_menu_markup(current_lang, i18n)
        )


async def notify_admins_about_receipt(bot: Bot, payment_id: int, user: types.User, photo_file_id: str):
    """Notify admins about a new receipt upload"""
    try:
        from config.settings import get_settings
        settings = get_settings()
        
        # Get user info
        user_info = f"User {user.id}"
        if user.username:
            user_info += f" (@{user.username})"
        elif user.first_name:
            user_info += f" ({user.first_name})"
        
        # Create admin notification message
        admin_message = (
            f"📸 <b>Новый чек для проверки</b>\n\n"
            f"👤 {user_info}\n"
            f"🆔 Payment ID: {payment_id}\n"
            f"📅 Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"Проверьте чек и подтвердите или отклоните платеж."
        )
        
        # Send to all admins
        for admin_id in settings.ADMIN_IDS:
            try:
                # Send photo with caption
                await bot.send_photo(
                    chat_id=admin_id,
                    photo=photo_file_id,
                    caption=admin_message,
                    parse_mode="HTML"
                )
                
                # Send approval/rejection keyboard
                from bot.keyboards.inline.admin_keyboards import get_phone_transfer_approval_keyboard
                await bot.send_message(
                    chat_id=admin_id,
                    text="Выберите действие:",
                    reply_markup=get_phone_transfer_approval_keyboard(payment_id)
                )
            except Exception as e:
                logging.error(f"Failed to notify admin {admin_id} about receipt: {e}")
                
    except Exception as e:
        logging.error(f"Error notifying admins about receipt: {e}")


@router.callback_query(F.data == "phone_transfer_pending")
async def phone_transfer_pending_handler(callback: types.CallbackQuery, i18n_data: dict):
    """Handle callback when user clicks on pending payment button"""
    current_lang = i18n_data.get("current_language", "ru")
    i18n: Optional[JsonI18n] = i18n_data.get("i18n_instance")

    get_text = lambda key, **kwargs: i18n.gettext(current_lang, key, **kwargs) if i18n else key

    await callback.answer(
        get_text("phone_transfer_payment_pending", 
                default="⏳ Ваш платеж находится на проверке у администратора. Обычно проверка занимает несколько минут."),
        show_alert=True
    )

