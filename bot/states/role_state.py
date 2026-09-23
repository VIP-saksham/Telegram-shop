# =============================================================================
#  Copyright (c) 2026 Saksham Swaroop (@truenakshu)  |  GitHub: VIP-saksham
#  LinkedIn: sakshamswaroop
#
#  All rights reserved. This source code is the private property of the
#  author. Copying, modifying, redistributing or deploying any part of this
#  file WITHOUT the author's written permission is strictly prohibited.
#  For licensing / permission: https://t.me/truenakshu
# =============================================================================

from aiogram.filters.state import StatesGroup, State


class RoleMgmtFSM(StatesGroup):
    waiting_role_name = State()
    waiting_role_perms = State()
    editing_role_name = State()
    editing_role_perms = State()
