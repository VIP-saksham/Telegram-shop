# =============================================================================
#  Copyright (c) 2026 Saksham Swaroop (@truenakshu)  |  GitHub: VIP-saksham
#  LinkedIn: sakshamswaroop
#
#  All rights reserved. This source code is the private property of the
#  author. Copying, modifying, redistributing or deploying any part of this
#  file WITHOUT the author's written permission is strictly prohibited.
#  For licensing / permission: https://t.me/truenakshu
# =============================================================================

from __future__ import annotations
from functools import lru_cache
from html import escape as _html_escape
from typing import Any

from bot.misc import EnvKeys
from .strings import TRANSLATIONS, DEFAULT_LOCALE
from bot.logger_mesh import logger


def esc(value: Any) -> str:
    """Escape a value for interpolation into a message."""
    return _html_escape("" if value is None else str(value), quote=False)


@lru_cache(maxsize=1)
def get_locale() -> str:
    loc = EnvKeys.BOT_LOCALE.lower().strip()
    return loc if loc in TRANSLATIONS else DEFAULT_LOCALE


# Per-chat locale overrides set from the Language menu. An asyncio task carries
# a context, so a value bound inside a handler is visible to every localize()
# call that handler (and its helpers) make while rendering that update.
import contextvars

_current_locale: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "current_locale", default=None,
)


def set_chat_locale(chat_id: int, locale: str) -> None:
    """Bind this update's language (validated by the caller).

    Bound on the context var, not a chat-id dict: localize() has no chat id
    parameter, and the context var flows through the handler's task only —
    no cross-chat bleed, no unbounded memory.
    """
    if locale in TRANSLATIONS:
        _current_locale.set(locale)


def localize(key: str, /, **kwargs: Any) -> str:
    """
    Get translation by key.
    Fallback: current-locale (if the update set one) -> default locale (env)
    -> DEFAULT_LOCALE -> the key itself.
    """
    loc = _current_locale.get() or get_locale()

    text = TRANSLATIONS.get(loc, {}).get(key)
    if text is None:
        text = TRANSLATIONS.get(DEFAULT_LOCALE, {}).get(key)
    if text is None:
        text = key

    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"Failed to format translation key '{key}' with kwargs {kwargs}: {e}")

    return str(text)
