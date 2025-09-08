from abc import ABC, abstractmethod
from aiogram import types

from sqlalchemy.ext.asyncio import AsyncSession


class InvoiceServiceInterface(ABC):
    @abstractmethod
    async def process_successful_payment(
        self,
        session: AsyncSession,
        message: types.Message,
        payment_db_id: int,
        months: int,
        stars_amount: int,
        currency: str,
        i18n_data: dict
    ) -> None:
        pass
