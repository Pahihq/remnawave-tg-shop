from dataclasses import dataclass
from typing import Optional


@dataclass
class SubscriptionOptions:
    duration: int
    price: Optional[int]

    def __gt__(self, other):
        return self.duration > other.duration
