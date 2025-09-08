from typing import Optional

from config.settings import Settings
from bot.services.yookassa_service import YooKassaService
from bot.services.yookassa_invoice_service import YookassaInvoiceService

class YookassaFactory:
    def create(
            self,
            shop_id: Optional[str],
            secret_key: Optional[str],
            configured_return_url: Optional[str],
            bot_username_for_default_return: Optional[str] = None,
            settings_obj: Optional[Settings] = None
    ):
        if settings_obj and settings_obj.WEBHOOK_BASE_URL:
            return YooKassaService(
                shop_id=shop_id,
                secret_key=secret_key,
                configured_return_url=configured_return_url,
                bot_username_for_default_return=bot_username_for_default_return,
                settings_obj=settings_obj,
            )
        else:
            return YookassaInvoiceService(
                shop_id=shop_id,
                secret_key=secret_key,
                configured_return_url=configured_return_url,
                bot_username_for_default_return=bot_username_for_default_return,
                settings_obj=settings_obj,
            )
