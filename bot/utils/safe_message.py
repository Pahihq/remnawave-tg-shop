import logging
from typing import Optional, Union
from aiogram import types
from aiogram.exceptions import TelegramBadRequest


async def safe_edit_message(
    message: types.Message, 
    text: str, 
    reply_markup=None, 
    parse_mode=None,
    disable_web_page_preview: Optional[bool] = None
) -> bool:
    """
    Safely edit message text, handling 'message is not modified' errors.
    
    Args:
        message: Telegram message to edit
        text: New text content
        reply_markup: New reply markup (optional)
        parse_mode: Parse mode for text (optional)
        disable_web_page_preview: Disable web page preview (optional)
    
    Returns:
        bool: True if message was edited successfully, False if not modified
    """
    try:
        await message.edit_text(
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
            disable_web_page_preview=disable_web_page_preview
        )
        return True
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            logging.debug("Message not modified, skipping edit")
            return False
        else:
            # Re-raise other Telegram errors
            raise
    except Exception as e:
        logging.error(f"Error editing message: {e}")
        raise


async def safe_edit_caption(
    message: types.Message,
    caption: str,
    reply_markup=None,
    parse_mode=None
) -> bool:
    """
    Safely edit message caption, handling 'message is not modified' errors.
    
    Args:
        message: Telegram message to edit
        caption: New caption text
        reply_markup: New reply markup (optional)
        parse_mode: Parse mode for text (optional)
    
    Returns:
        bool: True if caption was edited successfully, False if not modified
    """
    try:
        await message.edit_caption(
            caption=caption,
            reply_markup=reply_markup,
            parse_mode=parse_mode
        )
        return True
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            logging.debug("Message caption not modified, skipping edit")
            return False
        else:
            # Re-raise other Telegram errors
            raise
    except Exception as e:
        logging.error(f"Error editing message caption: {e}")
        raise


async def safe_edit_reply_markup(
    message: types.Message,
    reply_markup
) -> bool:
    """
    Safely edit message reply markup, handling 'message is not modified' errors.
    
    Args:
        message: Telegram message to edit
        reply_markup: New reply markup
    
    Returns:
        bool: True if markup was edited successfully, False if not modified
    """
    try:
        await message.edit_reply_markup(reply_markup=reply_markup)
        return True
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            logging.debug("Message reply markup not modified, skipping edit")
            return False
        else:
            # Re-raise other Telegram errors
            raise
    except Exception as e:
        logging.error(f"Error editing message reply markup: {e}")
        raise
