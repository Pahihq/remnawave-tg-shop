from aiogram import Router

from . import common
from . import broadcast
from .promo import promo_router_aggregate
from . import user_management
from . import statistics
from . import sync_admin
from . import logs_admin
from . import payments
from . import ads

admin_router_aggregate = Router(name="admin_features_router")

admin_router_aggregate.include_router(common.router)
admin_router_aggregate.include_router(broadcast.router)
admin_router_aggregate.include_router(promo_router_aggregate)
admin_router_aggregate.include_router(user_management.router)
admin_router_aggregate.include_router(statistics.router)
admin_router_aggregate.include_router(sync_admin.router)
admin_router_aggregate.include_router(logs_admin.router)
admin_router_aggregate.include_router(payments.router)
admin_router_aggregate.include_router(ads.router)

# Conditionally include phone_transfer_payments router if feature is enabled
try:
    from config.settings import get_settings
    settings = get_settings()
    if settings.PHONE_TRANSFER_ENABLED:
        from . import phone_transfer_payments
        admin_router_aggregate.include_router(phone_transfer_payments.router)
except Exception:
    # If settings fail or phone_transfer module doesn't exist, skip gracefully
    pass

__all__ = ("admin_router_aggregate", )
