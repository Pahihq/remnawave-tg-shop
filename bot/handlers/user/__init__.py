from aiogram import Router

from . import start
# TODO: after splitting subscription into a package, replace this import
from .subscription import router as subscription_router
from . import referral
from . import promo_user
from . import trial_handler

user_router_aggregate = Router(name="user_router_aggregate")

user_router_aggregate.include_router(promo_user.router)
user_router_aggregate.include_router(trial_handler.router)
user_router_aggregate.include_router(start.router)
user_router_aggregate.include_router(subscription_router)
user_router_aggregate.include_router(referral.router)

# Conditionally include phone_transfer_handler router if feature is enabled
try:
    from config.settings import get_settings
    settings = get_settings()
    if settings.PHONE_TRANSFER_ENABLED:
        from . import phone_transfer_handler
        user_router_aggregate.include_router(phone_transfer_handler.router)
except Exception:
    # If settings fail or phone_transfer module doesn't exist, skip gracefully
    pass
