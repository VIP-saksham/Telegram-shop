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
import re
from html import escape as esc

from aiogram.types import InlineKeyboardButton

# --- Button styles ---
SUCCESS = "success"   # green — buy / top-up / positive actions
PRIMARY = "primary"   # blue  — navigation, profile, back
DANGER = "danger"     # red   — admin entry, destructive actions

# --- Custom-emoji icon IDs ---
# Premium icons are rendered by Telegram only when the bot's owner holds
# Telegram Premium; plain labels still render fine without it.
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
    "plus": "5338147694833419938",        # add
    "minus": "5277627851903849306",       # remove
    "trash": "5373870726667027709",       # trash
    "search": "5362753053042400691",      # magnifier
    "users": "5438502501768771570",       # people
    "megaphone": "5316727448644103240",   # broadcast
    "gear": "5362753053042400692",        # settings
    "list": "5316727448644103241",        # list
    "crown": "5940938335731169331",       # crown
    "door": "5338147694833419939",        # exit
    "key": "5373870726667027710",         # key
    "chart": "5940938335731169332",       # stats
}

# Unicode emojis that used to live inside button labels. They are stripped
# from label text so that ONLY the premium custom-emoji icon shows next to
# the button name (no double-emoji look for users without premium).
DECOR_EMOJI = set(
    "🏪 🛒 📦 📂 👥 📝 🛡 🔧 🏷 ⛩️ ⛩ ✖ ✖️ ⬅ ➡ ⬆ ⬆️ ⬇ ⬇️ ◀ ▶ ◀️ ▶️ ⭐ 👤 📜 🆘 ℹ ℹ️ 💰 💳 💵 "
    "🎁 🔍 ♻ 🔴 🟢 🚫 ➖ ➕ 📋 🔑 ⚙ 🚀 💎 🔥 📊 🧾 🗑 🗑️ ✅ ❌ ⚠ ⚠️ 📌 🔒 📈 📉 👑 🎛 🎛️ 🧰 🖊 🖊️ "
    "✏ ✏️ 📅 🕒 🕐 💲 💲️ 🪙 🏦 🧑 👤‍👥 📤 📥 🎯 🏆 📖 🧹 💡 ❓ ℹ️ 🛍 🛍️ 💲❕".split()
)


def clean_label(text: str) -> str:
    """Drop decorative emoji from a button label, leaving the plain name.

    Keeps digits, letters, punctuation and all other symbols; collapses the
    whitespace left behind.  Used on every localized label before it goes
    into a button so the premium icon becomes the only pictogram.
    """
    if not text:
        return text
    out = []
    for ch in text:
        if ch in DECOR_EMOJI:
            continue
        out.append(ch)
    cleaned = "".join(out)
    # collapse runs of spaces and trim (also handles emoji glued to the text)
    return re.sub(r"\s{2,}", " ", cleaned).strip()


def cbtn(text: str, callback_data: str | None = None, *, url: str | None = None,
         color: str | None = None, icon: str | None = None) -> InlineKeyboardButton:
    """Clean label + premium icon + style — the standard button factory.

    This is what keyboards should use instead of raw kb.button(): the label
    is freed of unicode emoji (clean_label) and the pictogram comes solely
    from the custom-emoji icon.
    """
    kwargs: dict = {"text": clean_label(text)}
    if callback_data:
        kwargs["callback_data"] = callback_data
    if url:
        kwargs["url"] = url
    if color:
        kwargs["style"] = color
    if icon:
        kwargs["icon_custom_emoji_id"] = ICON.get(icon, icon)
    return InlineKeyboardButton(**kwargs)


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
