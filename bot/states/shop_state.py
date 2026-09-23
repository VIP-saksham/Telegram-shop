# =============================================================================
#  Copyright (c) 2026 Saksham Swaroop (@truenakshu)  |  GitHub: VIP-saksham
#  LinkedIn: sakshamswaroop
#
#  All rights reserved. This source code is the private property of the
#  author. Copying, modifying, redistributing or deploying any part of this
#  file WITHOUT the author's written permission is strictly prohibited.
#  For licensing / permission: https://t.me/truenakshu
# =============================================================================

from aiogram.filters.state import State, StatesGroup


class ShopStates(StatesGroup):
    """
    FSM states for the shopping section (personal purchases list).
    """
    viewing_goods = State()
    viewing_bought_items = State()
    viewing_categories = State()
    waiting_search_query = State()
    viewing_search_results = State()
