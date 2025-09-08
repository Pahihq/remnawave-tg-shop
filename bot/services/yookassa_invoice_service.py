from typing import Optional

from bot.contracts.yookassa_service_interface import YookassaServiceInterface
from config.settings import Settings


class YookassaInvoiceService(YookassaServiceInterface):
    def __init__(
        self,
        shop_id: Optional[str],
        secret_key: Optional[str],
        configured_return_url: Optional[str],
        bot_username_for_default_return: Optional[str] = None,
        settings_obj: Optional[Settings] = None
    ):
        pass

    async def create_payment(self):
        pass

    async def get_payment(self):
        pass
