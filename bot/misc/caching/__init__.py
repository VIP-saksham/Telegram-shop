# =============================================================================
#  Copyright (c) 2026 Saksham Swaroop (@truenakshu)  |  GitHub: VIP-saksham
#  LinkedIn: sakshamswaroop
#
#  All rights reserved. This source code is the private property of the
#  author. Copying, modifying, redistributing or deploying any part of this
#  file WITHOUT the author's written permission is strictly prohibited.
#  For licensing / permission: https://t.me/truenakshu
# =============================================================================

from bot.misc.caching.cache import (
    get_cache_manager, CacheManager, cache_result, init_cache_manager, single_flight,
)
from bot.misc.caching.cache_scheduler import CacheScheduler
from bot.misc.caching.storage import get_redis_storage

