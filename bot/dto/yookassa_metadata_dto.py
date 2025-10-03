from dataclasses import dataclass


@dataclass
class YookassaMetadata:
    user_id: str
    subscription_months: str
    payment_db_id: str
