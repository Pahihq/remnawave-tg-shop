from abc import ABC, abstractmethod
from typing import Optional

from config.settings import Settings


class YookassaServiceInterface(ABC):

    @abstractmethod
    def __init__(
        self,
        shop_id: Optional[str],
        secret_key: Optional[str],
        configured_return_url: Optional[str],
        bot_username_for_default_return: Optional[str] = None,
        settings_obj: Optional[Settings] = None
    ):
        self.shop_id = shop_id,
        self.secret_key = secret_key,
        self.configured_return_url = configured_return_url,
        self.bot_username_for_default_return = bot_username_for_default_return,
        self.settings_obj = settings_obj,

    @abstractmethod
    async def create_payment(self):
        """
        Must create new payment
        """
        pass

    @abstractmethod
    async def get_payment(self):
        """
        Get information about the payment
        """
        pass
