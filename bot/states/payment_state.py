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


class BalanceStates(StatesGroup):
    """FSM states for the balance top-up flow."""
    waiting_amount = State()
    waiting_payment = State()
    waiting_utr = State()
    waiting_screenshot = State()
    waiting_proof = State()
