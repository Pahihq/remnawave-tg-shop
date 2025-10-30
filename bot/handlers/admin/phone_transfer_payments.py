"""
Phone Transfer Payment Handlers - Isolated Module
This module contains all phone transfer payment handlers to minimize conflicts with upstream updates.
"""
import logging
from aiogram import Router, F, types
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import Settings
from db.models import PhoneTransferPayment
from bot.keyboards.inline.admin_keyboards import (
    get_back_to_admin_panel_keyboard,
    get_phone_transfer_approval_keyboard,
    get_phone_transfer_rejection_reason_keyboard
)
from bot.services.phone_transfer_service import PhoneTransferService
from bot.services.subscription_service import SubscriptionService
from bot.services.referral_service import ReferralService
from bot.services.panel_api_service import PanelApiService
from bot.middlewares.i18n import JsonI18n
from bot.utils.safe_message import safe_edit_message
from aiogram import Bot

router = Router(name="admin_phone_transfer_payments_router")


@router.callback_query(F.data.startswith("approve_phone_transfer:"))
async def approve_phone_transfer_handler(
        callback: types.CallbackQuery, i18n_data: dict, session: AsyncSession,
        phone_transfer_service: PhoneTransferService, subscription_service: SubscriptionService,
        referral_service: ReferralService, panel_service: PanelApiService):
    """Approve a phone transfer payment"""
    current_lang = i18n_data.get("current_language", "ru")
    i18n: Optional[JsonI18n] = i18n_data.get("i18n_instance")
    
    if not i18n or not callback.message:
        await callback.answer("Error processing request.", show_alert=True)
        return
    
    try:
        payment_id = int(callback.data.split(":")[-1])
        logging.info(f"Admin {callback.from_user.id} attempting to approve phone transfer payment {payment_id}")
    except (ValueError, IndexError):
        await callback.answer("Invalid payment ID.", show_alert=True)
        return
    
    # Get payment details
    payment = await session.get(PhoneTransferPayment, payment_id)
    if not payment:
        logging.error(f"Payment {payment_id} not found in database")
        await callback.answer("Payment not found.", show_alert=True)
        return
    
    if payment.status != "pending":
        logging.warning(f"Payment {payment_id} is not in pending status. Current status: {payment.status}")
        await callback.answer("Payment is not in pending status.", show_alert=True)
        return
    
    logging.info(f"Approving payment {payment_id} for user {payment.user_id}")
    
    # Approve payment
    success = await phone_transfer_service.approve_payment(
        session, payment_id, callback.from_user.id, "Approved by admin"
    )
    
    if not success:
        logging.error(f"Failed to approve payment {payment_id} via phone_transfer_service")
        await callback.answer("Failed to approve payment.", show_alert=True)
        return
    
    logging.info(f"Payment {payment_id} approved successfully, now activating subscription")
    
    # Activate subscription
    try:
        activation_details = await subscription_service.activate_subscription(
            session,
            payment.user_id,
            payment.subscription_duration_months,
            payment.amount,
            None,  # No payment_id for phone transfer
            promo_code_id_from_payment=payment.promo_code_id,
            provider="phone_transfer"
        )
        
        if not activation_details or not activation_details.get('end_date'):
            logging.error(f"Failed to activate subscription for payment {payment_id}")
            await callback.answer("Failed to activate subscription.", show_alert=True)
            return
        
        logging.info(f"Subscription activated successfully for payment {payment_id}")
        
        # Apply referral bonuses if applicable
        try:
            await referral_service.apply_referral_bonuses_for_payment(
                session, payment.user_id, payment.subscription_duration_months
            )
            logging.info(f"Referral bonuses applied for payment {payment_id}")
        except Exception as ref_error:
            logging.warning(f"Failed to apply referral bonuses for payment {payment_id}: {ref_error}")
        
        # Notify user about successful payment
        logging.info(f"Attempting to notify user {payment.user_id} about approved payment {payment_id}")
        await notify_user_about_approved_payment(
            callback.bot, payment, activation_details
        )
        
        # Update admin message
        await safe_edit_message(
            callback.message,
            f"✅ Платеж {payment_id} подтвержден!\n"
            f"Подписка активирована для пользователя {payment.user_id}.\n"
            f"Срок: {payment.subscription_duration_months} мес.\n"
            f"Сумма: {payment.amount} {payment.currency}",
            reply_markup=get_back_to_admin_panel_keyboard(current_lang, i18n)
        )
        
        await callback.answer("Payment approved successfully!")
        logging.info(f"Payment {payment_id} approval process completed successfully")
        
    except Exception as e:
        logging.error(f"Error activating subscription for phone transfer payment {payment_id}: {e}")
        await callback.answer("Payment approved but subscription activation failed.", show_alert=True)


@router.callback_query(F.data.startswith("reject_phone_transfer:"))
async def reject_phone_transfer_handler(
        callback: types.CallbackQuery, i18n_data: dict, session: AsyncSession,
        phone_transfer_service: PhoneTransferService):
    """Show rejection reason selection for phone transfer payment"""
    current_lang = i18n_data.get("current_language", "ru")
    i18n: Optional[JsonI18n] = i18n_data.get("i18n_instance")
    
    if not i18n or not callback.message:
        await callback.answer("Error processing request.", show_alert=True)
        return
    
    try:
        payment_id = int(callback.data.split(":")[-1])
    except (ValueError, IndexError):
        await callback.answer("Invalid payment ID.", show_alert=True)
        return
    
    # Show rejection reason keyboard
    reply_markup = get_phone_transfer_rejection_reason_keyboard(payment_id)
    await safe_edit_message(
        callback.message,
        "Выберите причину отклонения платежа:",
        reply_markup=reply_markup
    )
    
    await callback.answer()


@router.callback_query(F.data.startswith("reject_reason:"))
async def reject_reason_handler(
        callback: types.CallbackQuery, i18n_data: dict, session: AsyncSession,
        phone_transfer_service: PhoneTransferService):
    """Handle rejection reason selection and reject payment"""
    current_lang = i18n_data.get("current_language", "ru")
    i18n: Optional[JsonI18n] = i18n_data.get("i18n_instance")
    
    if not i18n or not callback.message:
        await callback.answer("Error processing request.", show_alert=True)
        return
    
    try:
        _, payment_id_str, reason_code = callback.data.split(":")
        payment_id = int(payment_id_str)
        logging.info(f"Admin {callback.from_user.id} attempting to reject phone transfer payment {payment_id} with reason: {reason_code}")
    except (ValueError, IndexError):
        await callback.answer("Invalid data.", show_alert=True)
        return
    
    # Map reason codes to human-readable text
    reason_map = {
        "wrong_amount": "Неверная сумма перевода",
        "wrong_recipient": "Неверный номер получателя",
        "unreadable_receipt": "Чек нечитаем или неполный",
        "wrong_date": "Неверная дата перевода",
        "other_reason": "Другая причина"
    }
    
    reason_text = reason_map.get(reason_code, "Неизвестная причина")
    
    # Reject payment
    success = await phone_transfer_service.reject_payment(
        session, payment_id, callback.from_user.id, reason_text, f"Rejected by admin: {reason_text}"
    )
    
    if not success:
        logging.error(f"Failed to reject payment {payment_id} via phone_transfer_service")
        await callback.answer("Failed to reject payment.", show_alert=True)
        return
    
    logging.info(f"Payment {payment_id} rejected successfully, now notifying user")
    
    # Get payment details for user notification
    payment = await session.get(PhoneTransferPayment, payment_id)
    if payment:
        # Notify user about rejected payment
        await notify_user_about_rejected_payment(
            callback.bot, payment, reason_text
        )
        logging.info(f"User {payment.user_id} notified about rejected payment {payment_id}")
    else:
        logging.warning(f"Payment {payment_id} not found when trying to notify user")
    
    # Update admin message
    await safe_edit_message(
        callback.message,
        f"❌ Платеж {payment_id} отклонен!\n"
        f"Причина: {reason_text}\n"
        f"Пользователь уведомлен об отклонении.",
        reply_markup=get_back_to_admin_panel_keyboard(current_lang, i18n)
    )
    
    await callback.answer("Payment rejected successfully!")
    logging.info(f"Payment {payment_id} rejection process completed successfully")


@router.callback_query(F.data.startswith("view_phone_transfer:"))
async def view_phone_transfer_handler(
        callback: types.CallbackQuery, i18n_data: dict, session: AsyncSession):
    """View detailed information about phone transfer payment"""
    current_lang = i18n_data.get("current_language", "ru")
    i18n: Optional[JsonI18n] = i18n_data.get("i18n_instance")
    
    if not i18n or not callback.message:
        await callback.answer("Error processing request.", show_alert=True)
        return
    
    try:
        payment_id = int(callback.data.split(":")[-1])
        logging.info(f"Admin {callback.from_user.id} viewing phone transfer payment {payment_id}")
    except (ValueError, IndexError):
        await callback.answer("Invalid payment ID.", show_alert=True)
        return
    
    # Get payment details
    payment = await session.get(PhoneTransferPayment, payment_id)
    if not payment:
        logging.error(f"Payment {payment_id} not found when admin tried to view it")
        await callback.answer("Payment not found.", show_alert=True)
        return
    
    logging.info(f"Payment {payment_id} details retrieved successfully for admin view")
    
    # Format payment details
    user_info = f"User {payment.user_id}"
    if payment.user and payment.user.username:
        user_info += f" (@{payment.user.username})"
    elif payment.user and payment.user.first_name:
        user_info += f" ({payment.user.first_name})"
    
    payment_date = payment.created_at.strftime('%Y-%m-%d %H:%M') if payment.created_at else "N/A"
    
    details_text = (
        f"📱 <b>Детали платежа по переводу</b>\n\n"
        f"🆔 ID: {payment.payment_id}\n"
        f"👤 {user_info}\n"
        f"💰 Сумма: {payment.amount} {payment.currency}\n"
        f"📅 Срок подписки: {payment.subscription_duration_months} мес.\n"
        f"📅 Дата создания: {payment_date}\n"
        f"📋 Статус: {payment.status}\n"
        f"📝 Описание: {payment.description or 'N/A'}\n"
    )
    
    if payment.receipt_photo_id:
        details_text += f"\n📸 Чек загружен: Да"
    
    if payment.admin_notes:
        details_text += f"\n📝 Заметки админа: {payment.admin_notes}"
    
    # Show details with approval keyboard
    reply_markup = get_phone_transfer_approval_keyboard(payment_id)
    await safe_edit_message(
        callback.message,
        details_text,
        reply_markup=reply_markup,
        parse_mode="HTML"
    )
    
    await callback.answer()
    logging.info(f"Payment {payment_id} details displayed to admin successfully")


@router.callback_query(F.data.startswith("cancel_rejection:"))
async def cancel_rejection_handler(
        callback: types.CallbackQuery, i18n_data: dict, session: AsyncSession):
    """Cancel payment rejection and return to approval keyboard"""
    current_lang = i18n_data.get("current_language", "ru")
    i18n: Optional[JsonI18n] = i18n_data.get("i18n_instance")
    
    if not i18n or not callback.message:
        await callback.answer("Error processing request.", show_alert=True)
        return
    
    try:
        payment_id = int(callback.data.split(":")[-1])
        logging.info(f"Admin {callback.from_user.id} cancelled rejection for payment {payment_id}")
    except (ValueError, IndexError):
        await callback.answer("Invalid payment ID.", show_alert=True)
        return
    
    # Get payment details
    payment = await session.get(PhoneTransferPayment, payment_id)
    if not payment:
        await callback.answer("Payment not found.", show_alert=True)
        return
    
    # Show approval keyboard again
    reply_markup = get_phone_transfer_approval_keyboard(payment_id)
    await safe_edit_message(
        callback.message,
        f"📱 <b>Платеж по переводу {payment_id}</b>\n\n"
        f"👤 User {payment.user_id}\n"
        f"💰 Сумма: {payment.amount} {payment.currency}\n"
        f"📅 Срок: {payment.subscription_duration_months} мес.\n"
        f"📋 Статус: {payment.status}\n\n"
        "Выберите действие:",
        reply_markup=reply_markup,
        parse_mode="HTML"
    )
    
    await callback.answer("Rejection cancelled")
    logging.info(f"Rejection cancelled for payment {payment_id}, returned to approval keyboard")


async def notify_user_about_approved_payment(
        bot: Bot, payment: PhoneTransferPayment, activation_details: dict):
    """Notify user about approved phone transfer payment"""
    try:
        logging.info(f"Attempting to notify user {payment.user_id} about approved payment {payment.payment_id}")
        
        user_lang = "ru"  # Default language
        if payment.user and payment.user.language_code:
            user_lang = payment.user.language_code
        
        # Get i18n instance
        from bot.middlewares.i18n import JsonI18n
        i18n = JsonI18n()
        
        _ = lambda key, **kwargs: i18n.gettext(user_lang, key, **kwargs)
        
        config_link = activation_details.get("subscription_url") or _("config_link_not_available")
        
        message_text = _(
            "phone_transfer_payment_approved",
            default="✅ Ваш платеж по переводу подтвержден!\n\n"
            f"Подписка на {payment.subscription_duration_months} мес. активирована.\n"
            f"Активна до: {activation_details['end_date'].strftime('%Y-%m-%d')}\n\n"
            f"Ключ подключения:\n<code>{config_link}</code>\n\n"
            "Чтобы подключиться, перейдите по ссылке и следуйте инструкции 👇"
        )
        
        # Get keyboard
        from bot.keyboards.inline.user_keyboards import get_connect_and_main_keyboard
        from config.settings import get_settings
        settings = get_settings()
        
        reply_markup = get_connect_and_main_keyboard(
            user_lang, i18n, settings, config_link
        )
        
        # Send message to user
        sent_message = await bot.send_message(
            payment.user_id,
            message_text,
            reply_markup=reply_markup,
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        
        logging.info(f"Successfully notified user {payment.user_id} about approved payment {payment.payment_id}. Message ID: {sent_message.message_id}")
        
    except Exception as e:
        logging.error(f"Error notifying user {payment.user_id} about approved phone transfer payment {payment.payment_id}: {e}")
        # Try to send a simple message without markup
        try:
            await bot.send_message(
                payment.user_id,
                f"✅ Ваш платеж по переводу подтвержден! Подписка активирована на {payment.subscription_duration_months} мес.",
                parse_mode="HTML"
            )
            logging.info(f"Sent fallback notification to user {payment.user_id}")
        except Exception as fallback_error:
            logging.error(f"Failed to send fallback notification to user {payment.user_id}: {fallback_error}")


async def notify_user_about_rejected_payment(
        bot: Bot, payment: PhoneTransferPayment, reason: str):
    """Notify user about rejected phone transfer payment"""
    try:
        logging.info(f"Attempting to notify user {payment.user_id} about rejected payment {payment.payment_id}")
        
        user_lang = "ru"  # Default language
        if payment.user and payment.user.language_code:
            user_lang = payment.user.language_code
        
        # Get i18n instance
        from bot.middlewares.i18n import JsonI18n
        i18n = JsonI18n()
        
        _ = lambda key, **kwargs: i18n.gettext(user_lang, key, **kwargs)
        
        message_text = _(
            "phone_transfer_payment_rejected",
            default="❌ Ваш платеж по переводу отклонен.\n\n"
            f"Причина: {reason}\n\n"
            "Пожалуйста, проверьте детали перевода и попробуйте еще раз.\n"
            "Если у вас есть вопросы, обратитесь в поддержку."
        )
        
        # Get keyboard
        from bot.keyboards.inline.user_keyboards import get_back_to_main_menu_markup
        
        reply_markup = get_back_to_main_menu_markup(user_lang, i18n)
        
        # Send message to user
        sent_message = await bot.send_message(
            payment.user_id,
            message_text,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
        
        logging.info(f"Successfully notified user {payment.user_id} about rejected payment {payment.payment_id}. Message ID: {sent_message.message_id}")
        
    except Exception as e:
        logging.error(f"Error notifying user {payment.user_id} about rejected phone transfer payment {payment.payment_id}: {e}")
        # Try to send a simple message without markup
        try:
            await bot.send_message(
                payment.user_id,
                f"❌ Ваш платеж по переводу отклонен. Причина: {reason}",
                parse_mode="HTML"
            )
            logging.info(f"Sent fallback rejection notification to user {payment.user_id}")
        except Exception as fallback_error:
            logging.error(f"Failed to send fallback rejection notification to user {payment.user_id}: {fallback_error}")

