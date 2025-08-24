import math
from typing import List

from aiogram.types import InlineKeyboardButton


def get_pagination_buttons(
    total_amount: int,
    page_size: int,
    current_page: int,
    callback_data: str,
    lang: str,
    i18n_instance
) -> List[InlineKeyboardButton]:
    """
    Create pagination buttons
    create callback_data like f'callback_data{page}'
    """
    _ = lambda key, **kwargs: i18n_instance.gettext(lang, key, **kwargs)
    pagination_buttons = []
    if total_amount > page_size:
        total_pages = math.ceil(total_amount / page_size)
        if current_page > 0:
            pagination_buttons.append(
                InlineKeyboardButton(
                    text=_("prev_page_button"),
                    callback_data=f"{callback_data}{current_page - 1}"
                ))
        pagination_buttons.append(
            InlineKeyboardButton(text=f"{current_page + 1}/{total_pages}",
                                 callback_data="stub_page_display"))
        if current_page < total_pages - 1:
            pagination_buttons.append(
                InlineKeyboardButton(
                    text=_("next_page_button"),
                    callback_data=f"{callback_data}{current_page + 1}"
                ))
    return pagination_buttons


