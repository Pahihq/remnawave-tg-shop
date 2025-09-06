from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class SubscriptionOptions:
    duration: int
    price: Optional[int]

    def __gt__(self, other):
        return self.duration > other.duration


@dataclass
class SubscriptionDetails:
    end_date: Optional[datetime]
    status_from_panel: str
    config_link: Optional[str]
    traffic_limit_bytes: Optional[int]
    traffic_used_bytes: Optional[int]
    user_bot_username: Optional[str]
    is_panel_data: bool = False