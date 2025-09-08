from typing import Dict, Optional

from bot.contracts.invoice_service_interface import InvoiceServiceInterface


class InvoiceServiceRepository:
    """
    Repository for Invoice Service instances access
    """
    def __init__(self, services: Dict[str, InvoiceServiceInterface]) -> None:
        self.__services = services

    def get(self, service_name: str) -> Optional[InvoiceServiceInterface]:
        """
        Get invoice service by name
        """
        return self.__services.get(service_name)
