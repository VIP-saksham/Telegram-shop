# =============================================================================
#  Copyright (c) 2026 Saksham Swaroop (@truenakshu)  |  GitHub: VIP-saksham
#  LinkedIn: sakshamswaroop
#
#  All rights reserved. This source code is the private property of the
#  author. Copying, modifying, redistributing or deploying any part of this
#  file WITHOUT the author's written permission is strictly prohibited.
#  For licensing / permission: https://t.me/truenakshu
# =============================================================================

from aiogram import Dispatcher

from bot.handlers.admin import router as admin_router
from bot.handlers.other import router as other_router
from bot.handlers.user import router as user_router


def register_all_handlers(dp: Dispatcher) -> None:
    dp.include_router(admin_router)
    dp.include_router(other_router)
    dp.include_router(user_router)
