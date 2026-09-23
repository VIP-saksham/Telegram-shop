"""EagleX-inspired (not copied) UI design system: colored buttons + premium icons.

Colors:  success (green)  |  primary (blue)  |  danger (red)
Our scheme: green = buy/positive actions, blue = navigation & back,
red = admin entry & destructive actions.

Icons are custom-emoji IDs; `icon_custom_emoji_id` renders when the bot's
owner has Telegram Premium (or a collectible username), otherwise the plain
text label is shown and nothing breaks.
"""
from aiogram.types import InlineKeyboardButton

# --- Button styles (Bot API "style" field) ---
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
}


def btn(text: str, callback_data: str | None = None, *, url: str | None = None,
        color: str | None = None, icon: str | None = None) -> InlineKeyboardButton:
    """Build an InlineKeyboardButton with EagleX-inspired styling.

    color: SUCCESS / PRIMARY / DANGER (None = app default)
    icon:  key into ICON (or a raw custom-emoji id string)
    """
    kwargs = {"text": text}
    if callback_data:
        kwargs["callback_data"] = callback_data
    if url:
        kwargs["url"] = url
    if color:
        kwargs["style"] = color
    if icon:
        kwargs["icon_custom_emoji_id"] = ICON.get(icon, icon)
    return InlineKeyboardButton(**kwargs)
