import math

from aiogram.utils.keyboard import InlineKeyboardBuilder, InlineKeyboardButton
from aiogram.types import InlineKeyboardMarkup, WebAppInfo
from typing import Dict, Optional, List

from bot.dto.subscription_dto import SubscriptionOptions
from bot.helpers.keyboard_helpers import get_pagination_buttons
from config.settings import Settings


def get_main_menu_inline_keyboard(
        lang: str,
        i18n_instance,
        settings: Settings,
        show_trial_button: bool = False) -> InlineKeyboardMarkup:
    _ = lambda key, **kwargs: i18n_instance.gettext(lang, key, **kwargs)
    builder = InlineKeyboardBuilder()

    if show_trial_button and settings.TRIAL_ENABLED:
        builder.row(
            InlineKeyboardButton(text=_(key="menu_activate_trial_button"),
                                 callback_data="main_action:request_trial"))

    builder.row(
        InlineKeyboardButton(text=_(key="menu_subscribe_inline"),
                             callback_data="main_action:subscribe"))
    if settings.SUBSCRIPTION_MINI_APP_URL:
        builder.row(
            InlineKeyboardButton(
                text=_(key="menu_my_subscription_inline"),
                web_app=WebAppInfo(url=settings.SUBSCRIPTION_MINI_APP_URL),
            )
        )
    else:
        builder.row(
            InlineKeyboardButton(
                text=_(key="menu_my_subscription_inline"),
                callback_data="main_action:my_subscription",
            )
        )

    referral_button = InlineKeyboardButton(
        text=_(key="menu_referral_inline"),
        callback_data="main_action:referral")
    promo_button = InlineKeyboardButton(
        text=_(key="menu_apply_promo_button"),
        callback_data="main_action:apply_promo")
    builder.row(referral_button, promo_button)

    language_button = InlineKeyboardButton(
        text=_(key="menu_language_settings_inline"),
        callback_data="main_action:language")
    status_button_list = []
    if settings.SERVER_STATUS_URL:
        status_button_list.append(
            InlineKeyboardButton(text=_(key="menu_server_status_button"),
                                 url=settings.SERVER_STATUS_URL))

    if status_button_list:
        builder.row(language_button, *status_button_list)
    else:
        builder.row(language_button)

    if settings.SUPPORT_LINK:
        builder.row(
            InlineKeyboardButton(text=_(key="menu_support_button"),
                                 url=settings.SUPPORT_LINK))

    if settings.TERMS_OF_SERVICE_URL:
        builder.row(
            InlineKeyboardButton(text=_(key="menu_terms_button"),
                                 url=settings.TERMS_OF_SERVICE_URL))

    return builder.as_markup()


def get_language_selection_keyboard(i18n_instance,
                                    current_lang: str) -> InlineKeyboardMarkup:
    _ = lambda key, **kwargs: i18n_instance.gettext(current_lang, key, **kwargs
                                                    )
    builder = InlineKeyboardBuilder()
    builder.button(text=f"🇬🇧 English {'✅' if current_lang == 'en' else ''}",
                   callback_data="set_lang_en")
    builder.button(text=f"🇷🇺 Русский {'✅' if current_lang == 'ru' else ''}",
                   callback_data="set_lang_ru")
    builder.button(text=_(key="back_to_main_menu_button"),
                   callback_data="main_action:back_to_main")
    builder.adjust(1)
    return builder.as_markup()


def get_trial_confirmation_keyboard(lang: str,
                                    i18n_instance) -> InlineKeyboardMarkup:
    _ = lambda key, **kwargs: i18n_instance.gettext(lang, key, **kwargs)
    builder = InlineKeyboardBuilder()
    builder.button(text=_(key="trial_confirm_activate_button"),
                   callback_data="trial_action:confirm_activate")
    builder.button(text=_(key="cancel_button"),
                   callback_data="main_action:back_to_main")
    builder.adjust(1)
    return builder.as_markup()


def get_user_subscriptions_keyboard(
    subscriptions_ids: List[int],
    total_subscriptions: int,
    current_page: int,
    lang: str,
    i18n_instance,
    page_size: int = 5,
) -> InlineKeyboardMarkup:
    """
    Get keyboard markup with subscriptions name in format user_id
    """
    _ = lambda key, **kwargs: i18n_instance.gettext(lang, key, **kwargs)
    builder = InlineKeyboardBuilder()
    for subscriptions_id in subscriptions_ids:
        builder.button(text=str(subscriptions_id),callback_data=f"show_subscription:{subscriptions_id}")

    pagination_buttons = get_pagination_buttons(
        total_subscriptions,
        page_size,
        current_page,
        "main_action:my_subscription:",
        lang,
        i18n_instance,
    )
    builder.adjust(1)
    if pagination_buttons:
        builder.row(*pagination_buttons)

    back_keyboard = get_back_to_main_menu_markup(lang, i18n_instance)
    for row in back_keyboard.inline_keyboard:
        builder.row(*row)

    return builder.as_markup()


def get_subscription_options_keyboard(
    subscription_options: List[SubscriptionOptions],
    currency_symbol_val: str,
    subscription_id: Optional[id],
    lang: str,
    i18n_instance
) -> InlineKeyboardMarkup:
    _ = lambda key, **kwargs: i18n_instance.gettext(lang, key, **kwargs)
    builder = InlineKeyboardBuilder()
    if subscription_options:
        for item in subscription_options:
            if item.price is not None:
                button_text = _(
                    "subscribe_for_months_button",
                    months=item.duration,
                    price=item.price,
                    currency_symbol=currency_symbol_val
                )
                callback_data = f"subscribe_period:{item.duration}:{subscription_id}" if subscription_id else f"subscribe_period:{item.duration}"
                builder.button(
                    text=button_text,
                    callback_data=callback_data
                )
        builder.adjust(1)

    builder.row(
        InlineKeyboardButton(text=_(key="back_to_main_menu_button"),
                             callback_data="main_action:back_to_main"))
    return builder.as_markup()


def get_prolong_subscription_keyboard(
    subscription_id: int,
    lang: str,
    i18n_instance
):
    _ = lambda key, **kwargs: i18n_instance.gettext(lang, key, **kwargs)
    prolong_button = InlineKeyboardButton(
        text=_(key="prolong_subscription"),
        callback_data=f"main_action:subscribe:{subscription_id}"
    )
    back_markup = get_back_to_main_menu_markup(lang, i18n_instance)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [prolong_button],
            *back_markup.inline_keyboard,
        ]
    )

    return kb


def get_payment_method_keyboard(months: int, price: float,
                                tribute_url: Optional[str],
                                stars_price: Optional[int],
                                currency_symbol_val: str, lang: str,
                                i18n_instance, settings: Settings) -> InlineKeyboardMarkup:
    _ = lambda key, **kwargs: i18n_instance.gettext(lang, key, **kwargs)
    builder = InlineKeyboardBuilder()
    if settings.STARS_ENABLED and stars_price is not None:
        builder.button(text=_("pay_with_stars_button"),
                       callback_data=f"pay_stars:{months}:{stars_price}")
    if settings.TRIBUTE_ENABLED and tribute_url:
        builder.button(text=_("pay_with_tribute_button"), url=tribute_url)
    if settings.YOOKASSA_ENABLED:
        builder.button(text=_("pay_with_yookassa_button"),
                       callback_data=f"pay_yk:{months}:{price}")
    if settings.CRYPTOPAY_ENABLED:
        builder.button(text=_("pay_with_cryptopay_button"),
                       callback_data=f"pay_crypto:{months}:{price}")
    builder.button(text=_(key="cancel_button"),
                   callback_data="main_action:subscribe")
    builder.adjust(1)
    return builder.as_markup()


def get_payment_url_keyboard(payment_url: str, lang: str,
                             i18n_instance) -> InlineKeyboardMarkup:
    _ = lambda key, **kwargs: i18n_instance.gettext(lang, key, **kwargs)
    builder = InlineKeyboardBuilder()
    builder.button(text=_(key="pay_button"), url=payment_url)
    builder.button(text=_(key="back_to_main_menu_button"),
                   callback_data="main_action:back_to_main")
    builder.adjust(1)
    return builder.as_markup()


def get_referral_link_keyboard(lang: str,
                               i18n_instance) -> InlineKeyboardMarkup:
    _ = lambda key, **kwargs: i18n_instance.gettext(lang, key, **kwargs)
    builder = InlineKeyboardBuilder()
    builder.button(text=_(key="referral_share_message_button"),
                   callback_data="referral_action:share_message")
    builder.button(text=_(key="back_to_main_menu_button"),
                   callback_data="main_action:back_to_main")
    builder.adjust(1)
    return builder.as_markup()


def get_back_to_main_menu_markup(lang: str,
                                 i18n_instance) -> InlineKeyboardMarkup:
    _ = lambda key, **kwargs: i18n_instance.gettext(lang, key, **kwargs)
    builder = InlineKeyboardBuilder()
    builder.button(text=_(key="back_to_main_menu_button"),
                   callback_data="main_action:back_to_main")
    return builder.as_markup()


def get_subscribe_only_markup(lang: str, i18n_instance) -> InlineKeyboardMarkup:
    _ = lambda key, **kwargs: i18n_instance.gettext(lang, key, **kwargs)
    builder = InlineKeyboardBuilder()
    builder.button(text=_(key="menu_subscribe_inline"),
                   callback_data="main_action:subscribe")
    return builder.as_markup()


def get_user_banned_keyboard(support_link: Optional[str], lang: str,
                             i18n_instance) -> Optional[InlineKeyboardMarkup]:
    if not support_link:
        return None
    _ = lambda key, **kwargs: i18n_instance.gettext(lang, key, **kwargs)
    builder = InlineKeyboardBuilder()
    builder.button(text=_(key="menu_support_button"), url=support_link)
    return builder.as_markup()


def get_connect_and_main_keyboard(
        lang: str,
        i18n_instance,
        settings: Settings,
        config_link: Optional[str]) -> InlineKeyboardMarkup:
    """Keyboard with a connect button and a back to main menu button."""
    _ = lambda key, **kwargs: i18n_instance.gettext(lang, key, **kwargs)
    builder = InlineKeyboardBuilder()

    if settings.SUBSCRIPTION_MINI_APP_URL:
        builder.row(
            InlineKeyboardButton(
                text=_("connect_button"),
                web_app=WebAppInfo(url=settings.SUBSCRIPTION_MINI_APP_URL),
            )
        )
    elif config_link:
        builder.row(
            InlineKeyboardButton(text=_("connect_button"), url=config_link)
        )
    else:
        builder.row(
            InlineKeyboardButton(
                text=_("connect_button"),
                callback_data="main_action:my_subscription",
            )
        )

    builder.row(
        InlineKeyboardButton(
            text=_("back_to_main_menu_button"),
            callback_data="main_action:back_to_main",
        )
    )

    return builder.as_markup()
