import logging
from aiogram import Router, F, types, Bot
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from typing import Optional, Dict, Any, Union
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from bot.repositories.invoice_service_repository import InvoiceServiceRepository
from config.settings import Settings
from db.dal import payment_dal, subscription_dal
from bot.keyboards.inline.user_keyboards import (
    get_prolong_subscription_keyboard, get_subscription_options_keyboard,
    get_payment_method_keyboard,
    get_payment_url_keyboard,
    get_back_to_main_menu_markup,
    get_user_subscriptions_keyboard,
)
from bot.services.yookassa_service import YooKassaService
from bot.services.stars_service import StarsService
from bot.services.crypto_pay_service import CryptoPayService
from bot.services.subscription_service import SubscriptionService
from bot.services.panel_api_service import PanelApiService
from bot.services.referral_service import ReferralService
from bot.middlewares.i18n import JsonI18n
from db.dal.subscription_dal import get_subscription_by_user_id_and_subscription_uuid


router = Router(name="user_subscription_router")


async def display_subscription_options(
    event: Union[types.Message,
    types.CallbackQuery],
    i18n_data: dict, settings: Settings,
    session: AsyncSession,
):
    current_lang = i18n_data.get("current_language", settings.DEFAULT_LANGUAGE)
    i18n: Optional[JsonI18n] = i18n_data.get("i18n_instance")

    get_text = lambda key, **kwargs: i18n.gettext(
        current_lang, key, **kwargs,
    ) if i18n else key

    if not i18n:
        err_msg = "Language service error."
        if isinstance(event, types.CallbackQuery):
            await event.answer(err_msg, show_alert=True)
        elif isinstance(event, types.Message):
            await event.answer(err_msg)
        return

    subscription_id = event.data.split(":")[2] if isinstance(event, types.CallbackQuery) and len(event.data.split(":")) == 3 else None
    currency_symbol_val = settings.DEFAULT_CURRENCY_SYMBOL
    text_content = get_text(
        "select_subscription_period",
    ) if settings.subscription_options else get_text(
        "no_subscription_options_available",
    )

    reply_markup = get_subscription_options_keyboard(
        settings.subscription_options,
        currency_symbol_val,
        subscription_id,
        current_lang,
        i18n,
    ) if settings.subscription_options else get_back_to_main_menu_markup(
        current_lang, i18n,
    )

    target_message_obj = event.message if isinstance(
        event, types.CallbackQuery,
    ) else event
    if not target_message_obj:
        if isinstance(event, types.CallbackQuery):
            await event.answer(
                get_text("error_occurred_try_again"),
                show_alert=True,
            )
        return

    if isinstance(event, types.CallbackQuery):
        try:
            await target_message_obj.edit_text(
                text_content,
                reply_markup=reply_markup,
            )
        except Exception:
            await target_message_obj.answer(
                text_content,
                reply_markup=reply_markup,
            )
        await event.answer()
    else:
        await target_message_obj.answer(
            text_content,
            reply_markup=reply_markup,
        )


@router.callback_query(F.data.startswith("subscribe_period:"))
async def select_subscription_period_callback_handler(
    callback: types.CallbackQuery, settings: Settings, i18n_data: dict,
    session: AsyncSession,
):
    current_lang = i18n_data.get("current_language", settings.DEFAULT_LANGUAGE)
    i18n: Optional[JsonI18n] = i18n_data.get("i18n_instance")
    get_text = lambda key, **kwargs: i18n.gettext(
        current_lang, key, **kwargs,
    ) if i18n else key

    if not i18n or not callback.message:
        await callback.answer(
            get_text("error_occurred_try_again"),
            show_alert=True,
        )
        return

    try:
        months = int(callback.data.split(":")[-1])
    except (ValueError, IndexError):
        logging.error(
            f"Invalid subscription period in callback_data: {callback.data}",
        )
        await callback.answer(get_text("error_try_again"), show_alert=True)
        return

    subscription_options = SubscriptionService.find_dto_by_month(settings.subscription_options, months)
    price_rub = subscription_options.price if subscription_options else None
    if price_rub is None:
        logging.error(
            f"Price not found for {months} months subscription period in settings.subscription_options.",
        )
        await callback.answer(get_text("error_try_again"), show_alert=True)
        return

    currency_symbol_val = settings.DEFAULT_CURRENCY_SYMBOL
    text_content = get_text("choose_payment_method")
    tribute_url = settings.tribute_payment_links.get(months)
    subscription_options = SubscriptionService.find_dto_by_month(settings.stars_subscription_options, months)
    stars_price = subscription_options.price if subscription_options else None
    reply_markup = get_payment_method_keyboard(
        months,
        price_rub,
        tribute_url,
        stars_price,
        currency_symbol_val,
        current_lang,
        i18n,
        settings,
    )

    try:
        await callback.message.edit_text(
            text_content,
            reply_markup=reply_markup,
        )
    except Exception as e_edit:
        logging.warning(
            f"Edit message for payment method selection failed: {e_edit}. Sending new one.",
        )
        await callback.message.answer(
            text_content,
            reply_markup=reply_markup,
        )
    await callback.answer()


@router.callback_query(F.data.startswith("pay_stars:"))
async def pay_stars_callback_handler(
    callback: types.CallbackQuery, settings: Settings, i18n_data: dict,
    session: AsyncSession, bot: Bot, stars_service: StarsService,
):
    current_lang = i18n_data.get("current_language", settings.DEFAULT_LANGUAGE)
    i18n: Optional[JsonI18n] = i18n_data.get("i18n_instance")

    get_text = lambda key, **kwargs: i18n.gettext(current_lang, key, **kwargs) if i18n else key

    if not i18n or not callback.message:
        await callback.answer(get_text("error_occurred_try_again"), show_alert=True)
        return

    try:
        _, data_payload = callback.data.split(":", 1)
        months_str, price_str = data_payload.split(":")
        months = int(months_str)
        stars_price = int(price_str)
    except (ValueError, IndexError):
        logging.error(f"Invalid pay_stars data in callback: {callback.data}")
        await callback.answer(get_text("error_try_again"), show_alert=True)
        return

    user_id = callback.from_user.id
    payment_description = get_text("payment_description_subscription", months=months)

    payment_id = await stars_service.create_invoice(
        session, user_id, months, stars_price, payment_description,
    )
    if payment_id is None:
        await callback.message.edit_text(get_text("error_payment_gateway"))
        await callback.answer(get_text("error_try_again"), show_alert=True)
        return

    await callback.answer()


@router.callback_query(F.data.startswith("pay_yk:"))
async def pay_yk_callback_handler(
    callback: types.CallbackQuery, settings: Settings, i18n_data: dict,
    yookassa_service: YooKassaService, session: AsyncSession,
):
    current_lang = i18n_data.get("current_language", settings.DEFAULT_LANGUAGE)
    i18n: Optional[JsonI18n] = i18n_data.get("i18n_instance")

    get_text = lambda key, **kwargs: i18n.gettext(
        current_lang, key, **kwargs,
    ) if i18n else key

    if not i18n or not callback.message:
        await callback.answer(
            get_text("error_occurred_try_again"),
            show_alert=True,
        )
        return

    if not yookassa_service or not yookassa_service.configured:
        logging.error("YooKassa service is not configured or unavailable.")
        target_msg_edit = callback.message
        await target_msg_edit.edit_text(
            get_text("payment_service_unavailable"),
        )
        await callback.answer(
            get_text("payment_service_unavailable_alert"),
            show_alert=True,
        )
        return

    try:
        _, data_payload = callback.data.split(":", 1)
        months_str, price_str = data_payload.split(":")
        months = int(months_str)
        price_rub = float(price_str)
    except (ValueError, IndexError):
        logging.error(
            f"Invalid pay_yk data in callback: {callback.data}",
        )
        await callback.answer(get_text("error_try_again"), show_alert=True)
        return

    user_id = callback.from_user.id

    payment_description = get_text(
        "payment_description_subscription",
        months=months,
    )
    currency_code_for_yk = "RUB"

    payment_record_data = {
        "user_id": user_id,
        "amount": price_rub,
        "currency": currency_code_for_yk,
        "status": "pending_yookassa",
        "description": payment_description,
        "subscription_duration_months": months,
        # TODO: передавать в callback id платежа, сменить id платежа на uui. "subscription_uuid":
    }
    db_payment_record = None
    try:
        db_payment_record = await payment_dal.create_payment_record(
            session, payment_record_data,
        )
        await session.commit()
        logging.info(
            f"Payment record {db_payment_record.payment_id} created for user {user_id} with status 'pending_yookassa'.",
        )
    except Exception as e_db_payment:
        await session.rollback()
        logging.error(
            f"Failed to create payment record in DB for user {user_id}: {e_db_payment}",
            exc_info=True,
        )
        await callback.message.edit_text(
            get_text("error_creating_payment_record"),
        )
        await callback.answer(get_text("error_try_again"), show_alert=True)
        return

    if not db_payment_record:
        await callback.message.edit_text(
            get_text("error_creating_payment_record"),
        )
        await callback.answer(get_text("error_try_again"), show_alert=True)
        return

    yookassa_metadata = {
        "user_id": str(user_id),
        "subscription_months": str(months),
        "payment_db_id": str(db_payment_record.payment_id),
    }
    receipt_email_for_yk = settings.YOOKASSA_DEFAULT_RECEIPT_EMAIL

    payment_response_yk = await yookassa_service.create_payment(
        amount=price_rub,
        currency=currency_code_for_yk,
        description=payment_description,
        metadata=yookassa_metadata,
        receipt_email=receipt_email_for_yk,
    )

    if payment_response_yk and payment_response_yk.get("confirmation_url"):
        try:
            await payment_dal.update_payment_status_by_db_id(
                session,
                payment_db_id=db_payment_record.payment_id,
                new_status=payment_response_yk.get("status", "pending"),
                yk_payment_id=payment_response_yk.get("id"),
            )
            await session.commit()
        except Exception as e_db_update_ykid:
            await session.rollback()
            logging.error(
                f"Failed to update payment record {db_payment_record.payment_id} with YK ID: {e_db_update_ykid}",
                exc_info=True,
            )
            await callback.message.edit_text(
                get_text("error_payment_gateway_link_failed"),
            )
            await callback.answer(get_text("error_try_again"), show_alert=True)
            return

        await callback.message.edit_text(
            get_text(key="payment_link_message", months=months),
            reply_markup=get_payment_url_keyboard(
                payment_response_yk["confirmation_url"], current_lang, i18n,
            ),
            disable_web_page_preview=False,
        )
    else:
        try:
            await payment_dal.update_payment_status_by_db_id(
                session, db_payment_record.payment_id, "failed_creation",
            )
            await session.commit()
        except Exception as e_db_fail_create:
            await session.rollback()
            logging.error(
                f"Additionally failed to update payment record to 'failed_creation': {e_db_fail_create}",
                exc_info=True,
            )

        logging.error(
            f"Failed to create payment in YooKassa for user {user_id}, payment_db_id {db_payment_record.payment_id}. "
            f"Response: {payment_response_yk}",
        )
        await callback.message.edit_text(get_text("error_payment_gateway"))

    await callback.answer()


@router.callback_query(F.data.startswith("pay_crypto:"))
async def pay_crypto_callback_handler(
    callback: types.CallbackQuery, settings: Settings, i18n_data: dict,
    cryptopay_service: CryptoPayService, session: AsyncSession,
):
    current_lang = i18n_data.get("current_language", settings.DEFAULT_LANGUAGE)
    i18n: Optional[JsonI18n] = i18n_data.get("i18n_instance")
    get_text = lambda key, **kwargs: i18n.gettext(current_lang, key, **kwargs) if i18n else key

    if not i18n or not callback.message:
        await callback.answer(get_text("error_occurred_try_again"), show_alert=True)
        return

    if not cryptopay_service or not cryptopay_service.configured:
        await callback.message.edit_text(get_text("payment_service_unavailable"))
        await callback.answer(get_text("payment_service_unavailable_alert"), show_alert=True)
        return

    try:
        _, data_payload = callback.data.split(":", 1)
        months_str, amount_str = data_payload.split(":")
        months = int(months_str)
        amount_val = float(amount_str)
    except (ValueError, IndexError):
        logging.error(f"Invalid pay_crypto data in callback: {callback.data}")
        await callback.answer(get_text("error_try_again"), show_alert=True)
        return

    user_id = callback.from_user.id
    description = get_text("payment_description_subscription", months=months)

    invoice_url = await cryptopay_service.create_invoice(
        session, user_id, months, amount_val, description,
    )
    if invoice_url:
        await callback.message.edit_text(
            get_text("payment_link_message", months=months),
            reply_markup=get_payment_url_keyboard(invoice_url, current_lang, i18n),
            disable_web_page_preview=False,
        )
    else:
        await callback.message.edit_text(get_text("error_payment_gateway"))
    await callback.answer()


@router.callback_query(F.data == "main_action:subscribe")
async def reshow_subscription_options_callback(
    callback: types.CallbackQuery,
    i18n_data: dict,
    settings: Settings,
    session: AsyncSession,
):
    await display_subscription_options(callback, i18n_data, settings, session)


@router.callback_query(F.data.startswith("show_subscription:"))
async def show_current_subscription_handler(
    callback: types.CallbackQuery,
    i18n_data: dict,
    settings: Settings,
    panel_service: PanelApiService,
    subscription_service: SubscriptionService,
    session: AsyncSession,
    bot: Bot,
):
    subscription_id = callback.data.split(':')[1]
    target = callback.message if isinstance(callback, types.CallbackQuery) else callback
    current_lang = i18n_data.get("current_language", settings.DEFAULT_LANGUAGE)
    i18n: JsonI18n = i18n_data.get("i18n_instance")
    get_text = lambda key, **kw: i18n.gettext(current_lang, key, **kw)
    if not subscription_id.isdigit():
        active = None
    else:
        active = await subscription_service.get_subscription_details(session, callback.from_user.id, int(subscription_id))
    if not active:
        text = get_text("subscription_not_active")

        buy_button = InlineKeyboardButton(
            text=get_text("menu_subscribe_inline", default="Купить"),
            callback_data="main_action:subscribe",
        )
        back_markup = get_back_to_main_menu_markup(current_lang, i18n)

        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [buy_button],
                *back_markup.inline_keyboard,
            ],
        )

        if isinstance(callback, types.CallbackQuery):
            await callback.answer()
            try:
                await callback.message.edit_text(text, reply_markup=kb)
            except:
                await callback.message.answer(text, reply_markup=kb)
        else:
            await callback.answer(text, reply_markup=kb)
        return

    end_date = active.end_date
    days_left = (
        (end_date.date() - datetime.now().date()).days
        if end_date else 0
    )
    text = get_text(
        "my_subscription_details",
        end_date=end_date.strftime("%Y-%m-%d") if end_date else "N/A",
        days_left=max(0, days_left),
        status=active.status_from_panel.capitalize() if active.status_from_panel else get_text("status_active").capitalize(),
        config_link=active.config_link or get_text("config_link_not_available"),
        traffic_limit=(
            f"{active.traffic_limit_bytes / 2 ** 30:.2f} GB"
            if active.traffic_limit_bytes
            else get_text("traffic_unlimited")
        ),
        traffic_used=(
            f"{active['traffic_used_bytes'] / 2 ** 30:.2f} GB"
            if active.traffic_used_bytes is not None
            else get_text("traffic_na")
        ),
    )
    markup = get_prolong_subscription_keyboard(1, current_lang, i18n)

    if isinstance(callback, types.CallbackQuery):
        await callback.answer()
        try:
            await callback.message.edit_text(text, reply_markup=markup, parse_mode="HTML", disable_web_page_preview=True)
        except:
            await bot.send_message(
                chat_id=target.chat.id, text=text, reply_markup=markup, parse_mode="HTML",
                disable_web_page_preview=True,
            )
    else:
        await target.answer(text, reply_markup=markup, parse_mode="HTML", disable_web_page_preview=True)


async def my_subscription_command_handler(
    event: Union[types.Message, types.CallbackQuery],
    i18n_data: dict,
    settings: Settings,
    panel_service: PanelApiService,
    subscription_service: SubscriptionService,
    session: AsyncSession,
    bot: Bot,
):
    """
    Show available user subscriptions
    """
    target = event.message if isinstance(event, types.CallbackQuery) else event
    current_lang = i18n_data.get("current_language", settings.DEFAULT_LANGUAGE)
    i18n: JsonI18n = i18n_data.get("i18n_instance")
    get_text = lambda key, **kw: i18n.gettext(current_lang, key, **kw)
    current_page = int(event.data.split(':')[2]) if len(event.data.split(':')) == 3 else 0

    if not i18n or not target:
        if isinstance(event, types.Message):
            await event.answer(get_text("error_occurred_try_again"))
        return

    if not panel_service or not subscription_service:
        await target.answer(get_text("error_service_unavailable"))
        return
    total_subscriptions = await subscription_dal.get_all_subscriptions_by_user_id_count(session, event.from_user.id)
    page_size = settings.LOGS_PAGE_SIZE

    # TODO: вынести логику с пагинацией, избавиться от хардкода
    offset = page_size * current_page
    subscriptions_ids = await subscription_dal.get_subscriptions_by_user_id(
        session,
        event.from_user.id,
        limit=page_size,
        offset=offset,
    )

    if not subscriptions_ids:
        text = get_text("subscription_not_active")
        buy_button = InlineKeyboardButton(
            text=get_text("menu_subscribe_inline", default="Купить"),
            callback_data="main_action:subscribe",
        )
        back_markup = get_back_to_main_menu_markup(current_lang, i18n)

        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [buy_button],
                *back_markup.inline_keyboard,
            ],
        )
        if isinstance(event, types.CallbackQuery):
            await event.message.edit_text(text, reply_markup=kb)

    text = get_text("active_subscriptions")

    markup = get_user_subscriptions_keyboard(
        subscriptions_ids,
        total_subscriptions,
        current_page,
        current_lang,
        i18n
    )

    if isinstance(event, types.CallbackQuery):
        await event.answer()
        try:
            await event.message.edit_text(text, reply_markup=markup, parse_mode="HTML", disable_web_page_preview=True)
        except:
            await bot.send_message(
                chat_id=target.chat.id, text=text, reply_markup=markup, parse_mode="HTML",
                disable_web_page_preview=True,
            )
    else:
        await target.answer(text, reply_markup=markup, parse_mode="HTML", disable_web_page_preview=True)


@router.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: types.PreCheckoutQuery):
    await pre_checkout_query.answer(ok=True)


@router.message(F.successful_payment)
async def successful_payment_handler(
    message: types.Message,
    settings: Settings,
    i18n_data: dict,
    session: AsyncSession,
    invoice_service_repository: InvoiceServiceRepository,
):
    sp = message.successful_payment
    if not sp:
        return

    payload = sp.invoice_payload or ""
    try:
        service, payment_id_str, months_str = payload.split(":")
        payment_db_id = int(payment_id_str)
        months = int(months_str)
    except (ValueError, IndexError):
        logging.error(f"Invalid invoice payload for stars payment: {payload}")
        return

    amount = sp.total_amount
    currency = sp.currency

    invoice_service = invoice_service_repository.get(service)
    if not invoice_service:
        logging.error(f"Cant find service for invoice payment: {payload}")

    await invoice_service.process_successful_payment(
        session, message, payment_db_id, months, amount, currency, i18n_data
    )


@router.message(Command("connect"))
async def connect_command_handler(
    message: types.Message, i18n_data: dict,
    settings: Settings,
    panel_service: PanelApiService,
    subscription_service: SubscriptionService,
    session: AsyncSession, bot: Bot,
):
    logging.info(f"User {message.from_user.id} used /connect command.")
    await my_subscription_command_handler(
        message, i18n_data, settings,
        panel_service, subscription_service,
        session, bot,
    )
