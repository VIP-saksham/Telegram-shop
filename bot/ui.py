"""Own-look UI design system — colored buttons + premium icons + text design.

=== Buttons (Bot API 2026 `style` field) ===
SUCCESS (green) — buy / top-up / confirm
PRIMARY (blue)  — navigation & information
DANGER (red)    — back from submenus, admin, destructive

`icon_custom_emoji_id` renders when the bot owner has Telegram Premium
(otherwise the plain label shows and nothing breaks).

=== Text (HTML) ===
The look is built from small primitives instead of long fixed strings:
banner()  — top screen banner with a name accent
rule()    — thin divider line
kv()      — «key · value» row with value emphasized
bar()     — 10-slot progress bar (stock, limits)
quote()   — italic blockquote line for hints
"""
from html import escape as esc

from aiogram.types import InlineKeyboardButton

# --- Button styles ---
SUCCESS = "success"   # green — buy / top-up / positive actions
PRIMARY = "primary"   # blue  — navigation, profile, back
DANGER = "danger"     # red   — admin entry, destructive actions

# --- Custom-emoji icon IDs ---
ICON = {
    "shop": "5258024802010026053",        # shopping bag
    "buy": "6059938317644862304",         # check
    "wallet": "5769403330761593044",      # wallet
    "history": "4947523534369850267",     # clock
    "invite": "5316727448644103237",      # gift
    "share": "6100307857721267700",       # link
    "copy": "5258024802010026053",        # bag (promo/copy fallback)
    "leaderboard": "5913702317667913862", # trophy
    "help": "5258185631355378853",        # question
    "policy": "5438502501768771568",      # shield
    "language": "4947307063723164934",    # globe
    "back": "4997256682972121121",        # back arrow
    "usdt": "5931266229942620658",        # dollar
    "star": "5794068520488670034",        # star
    "vpn": "6305200926139361417",         # lock
    "pencil": "5260399854500191689",      # pencil
    "box": "5362753053042400690",         # package
    "fire": "5336279388641436838",        # flame
    "cart": "5455918259979436457",        # cart
}


def btn(text: str, callback_data: str | None = None, *, url: str | None = None,
        color: str | None = None, icon: str | None = None) -> InlineKeyboardButton:
    """Build an InlineKeyboardButton with our styling.

    color: SUCCESS / PRIMARY / DANGER (None = no explicit style)
    icon:  key into ICON (or a raw custom-emoji id string)
    """
    kwargs: dict = {"text": text}
    if callback_data:
        kwargs["callback_data"] = callback_data
    if url:
        kwargs["url"] = url
    if color:
        kwargs["style"] = color
    if icon:
        kwargs["icon_custom_emoji_id"] = ICON.get(icon, icon)
    return InlineKeyboardButton(**kwargs)


RULE = "─────────────────"


def banner(title: str, hi: str | None = None) -> str:
    """Top-of-screen banner: small caps title, rule, optional greeting.

    The first word (glyph) is bold, the rest of the title is light-italic —
    gives every screen the same recognizable 'card' opening.
    """
    head = f"<b>{esc(title)}</b>"
    lines = [head, RULE]
    if hi:
        lines.append(f"<i>{hi}</i>")
    return "\n".join(lines)


def rule() -> str:
    return RULE


def kv(key: str, value: str, *, code: bool = False) -> str:
    """One info row: glyph-free key, middot, bold (or code) value."""
    v = f"<code>{esc(value)}</code>" if code else f"<b>{esc(value)}</b>"
    return f"{esc(key)} · {v}"


def bar(cur: int, total: int | None = None, width: int = 10) -> str:
    """▓▓▓░░░░░ progress bar. total None -> cur/width fill ratio."""
    if total:
        filled = round(width * (1 if total <= 0 else cur / total))
    else:
        filled = round(width * (0 if cur <= 0 else (1 if cur >= width else cur / width)))
    filled = max(0, min(width, filled))
    return "▓" * filled + "░" * (width - filled)


def quote(text: str) -> str:
    """Italic hint line under a screen body."""
    return f"<i>{esc(text)}</i>"
