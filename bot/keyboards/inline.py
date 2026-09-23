# =============================================================================
#  Copyright (c) 2026 Saksham Swaroop (@truenakshu)  |  GitHub: VIP-saksham
#  LinkedIn: sakshamswaroop
#
#  All rights reserved. This source code is the private property of the
#  author. Copying, modifying, redistributing or deploying any part of this
#  file WITHOUT the author's written permission is strictly prohibited.
#  For licensing / permission: https://t.me/truenakshu
# =============================================================================

from typing import Callable, Iterable, Tuple
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from bot.i18n import localize
from bot.database.models import Permission
from bot.misc import LazyPaginator # noqa: F401
from bot.ui import SUCCESS, PRIMARY, DANGER, ICON, btn, cbtn, clean_label


def header(title: str, subtitle: str = "") -> str:
    """Aesthetic screen header — bold card title + thin rule (our own look)."""
    lines = [f"<b>{title}</b>", "─────────────────"]
    if subtitle:
        lines.append(f"<i>{subtitle}</i>")
    return "\n".join(lines)

def main_menu(role: int, channel: str | None = None, helper: str | None = None) -> InlineKeyboardMarkup:
    """Home layout: green Browse CTA, 2-col utility grid, full-width Language.

    ┌────────────────────┐
    │   Browse Products  │  green
    ├─────────┬──────────┤
    │ Wallet  │ History  │  blue
    ├─────────┼──────────┤
    │ Invite  │ Leader   │  blue
    ├─────────┼──────────┤
    │ Help    │ Policy   │  blue
    ├─────────┴──────────┤
    │      Language      │  blue
    └────────────────────┘
    """
    kb = InlineKeyboardBuilder()
    kb.row(cbtn(localize("btn.shop"), "shop", color=SUCCESS, icon="shop"))
    kb.row(
        cbtn(localize("btn.wallet"), "profile", color=PRIMARY, icon="wallet"),
        cbtn(localize("btn.history"), "operation_history", color=PRIMARY, icon="history"),
    )
    kb.row(
        cbtn(localize("btn.invite"), "referral_system", color=PRIMARY, icon="invite"),
        cbtn(localize("btn.leaderboard"), "ref_leaderboard", color=PRIMARY, icon="leaderboard"),
    )
    kb.row(
        cbtn(localize("btn.help"), "help_menu", color=PRIMARY, icon="help"),
        cbtn(localize("btn.rules"), "rules", color=PRIMARY, icon="policy"),
    )
    kb.row(cbtn(localize("btn.language"), "change_language", color=PRIMARY, icon="language"))
    if channel:
        kb.row(cbtn(localize("btn.channel"), url=f"https://t.me/{channel.lstrip('@')}", color=PRIMARY, icon="share"))
    if helper:
        kb.row(cbtn(localize("btn.support"), url=f"tg://user?id={helper}", color=PRIMARY, icon="help"))
    if Permission.has_any_admin_perm(role):
        kb.row(cbtn(localize("btn.admin_menu"), "console", color=DANGER, icon="gear"))
    return kb.as_markup()


def profile_keyboard(referral_percent: int, user_items: int = 0, cart_count: int = 0) -> InlineKeyboardMarkup:
    """
    Profile keyboard — wallet-style: green top-up, blue navigation, red back.
    """
    kb = InlineKeyboardBuilder()
    kb.row(cbtn(localize("btn.replenish"), "replenish_balance", color=SUCCESS, icon="usdt"))
    if referral_percent != 0:
        kb.row(cbtn(localize("btn.referral"), "referral_system", color=PRIMARY, icon="invite"))
    if user_items != 0:
        kb.row(cbtn(localize("btn.purchased"), "bought_items", color=PRIMARY, icon="buy"))
    cart_text = localize("btn.cart", count=cart_count) if cart_count > 0 else localize("btn.cart_empty")
    kb.row(cbtn(cart_text, "cart", color=PRIMARY, icon="cart"))
    kb.row(cbtn(localize("btn.operation_history"), "operation_history", color=PRIMARY, icon="history"))
    kb.row(cbtn(localize("btn.redeem_promo"), "redeem_promo", color=PRIMARY, icon="copy"))
    kb.row(cbtn(localize("btn.back"), "back_to_menu", color=PRIMARY, icon="back"))
    return kb.as_markup()


def admin_console_keyboard(maintenance_mode: bool = False, role: int = 127) -> InlineKeyboardMarkup:
    """
    Admin panel — shows only buttons the user has permissions for.
    """
    kb = InlineKeyboardBuilder()
    if role & Permission.CATALOG_MANAGE:
        kb.row(cbtn(localize("admin.menu.shop"), "shop_management", color=PRIMARY, icon="shop"))
        kb.row(cbtn(localize("admin.menu.goods"), "goods_management", color=PRIMARY, icon="box"))
        kb.row(cbtn(localize("admin.menu.categories"), "categories_management", color=PRIMARY, icon="list"))
    if role & Permission.PROMO_MANAGE:
        kb.row(cbtn(localize("admin.menu.promo"), "promo_mgmt", color=PRIMARY, icon="star"))
    if role & Permission.USERS_MANAGE:
        kb.row(cbtn(localize("admin.menu.users"), "user_management", color=PRIMARY, icon="users"))
    if role & Permission.ADMINS_MANAGE:
        kb.row(cbtn(localize("admin.menu.roles"), "role_mgmt", color=PRIMARY, icon="crown"))
    if role & Permission.BROADCAST:
        kb.row(cbtn(localize("admin.menu.broadcast"), "send_message", color=PRIMARY, icon="megaphone"))
    if role & Permission.SETTINGS_MANAGE:
        kb.row(cbtn(localize("admin.fc.menu"), "force_channels", color=PRIMARY, icon="door"))
        maintenance_key = "admin.menu.maintenance_on" if maintenance_mode else "admin.menu.maintenance_off"
        kb.row(cbtn(localize(maintenance_key), "toggle_maintenance", color=DANGER, icon="gear"))
    kb.row(cbtn(localize("btn.back"), "back_to_menu", color=DANGER, icon="back"))
    return kb.as_markup()


def simple_buttons(buttons: Iterable[Tuple[str, str]], per_row: int = 1) -> InlineKeyboardMarkup:
    """
    Universal button assembly from (text, callback_data) — default blue look.
    Labels are emoji-cleaned; attach an icon via `icons` if desired.
    """
    kb = InlineKeyboardBuilder()
    for text, cb in buttons:
        kb.button(text=clean_label(text), callback_data=cb, style=PRIMARY)
    kb.adjust(per_row)
    return kb.as_markup()


def back(cb: str = "menu", text: str | None = None) -> InlineKeyboardMarkup:
    """
    One 'Back' button — blue (navigation) with back-arrow icon.
    """
    kb = InlineKeyboardBuilder()
    b = btn(text or localize("btn.back"), cb, color=PRIMARY, icon="back")
    kb.row(b)
    return kb.as_markup()


def close() -> InlineKeyboardMarkup:
    """
    One button 'Close' (blue pill).
    """
    return simple_buttons([(localize("btn.close"), "close")])


async def lazy_paginated_keyboard(
        paginator: 'LazyPaginator',
        item_text: Callable[[object], str],
        item_callback: Callable[[object], str],
        page: int = 0,
        back_cb: str | None = None,
        nav_cb_prefix: str = "",
        back_text: str | None = None,
        extra_rows: list[list[InlineKeyboardButton]] | None = None,
) -> InlineKeyboardMarkup:
    """
    Lazy pagination keyboard with data loading on demand.

    `extra_rows` are inserted between the item buttons and the navigation row.
    """
    kb = InlineKeyboardBuilder()

    # Get items for current page
    items = await paginator.get_page(page)

    for item in items:
        kb.button(text=item_text(item), callback_data=item_callback(item))
    kb.adjust(1)
    for row in (extra_rows or []):
        kb.row(*row)

    # Navigation
    total_pages = await paginator.get_total_pages()
    if total_pages > 1:
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton(text="‹", callback_data=f"{nav_cb_prefix}{page - 1}", style=PRIMARY))
        nav_buttons.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="dummy_button", style=PRIMARY))
        if page < total_pages - 1:
            nav_buttons.append(InlineKeyboardButton(text="›", callback_data=f"{nav_cb_prefix}{page + 1}", style=PRIMARY))
        kb.row(*nav_buttons)

    if back_cb:
        kb.row(InlineKeyboardButton(text=back_text or localize("btn.back"), callback_data=back_cb, style=PRIMARY))

    return kb.as_markup()


def item_info(
        back_data: str, avg_rating: float = None,
        review_count: int = 0, has_purchased: bool = False,
        applied_promo: str = None, reviews_enabled: bool = True,
        out_of_stock: bool = False, subscribed: bool = False,
        low_balance: bool = False,
) -> InlineKeyboardMarkup:
    """
    Product card — green Buy, blue extras, red Back.

    When `out_of_stock`, offers a restock notification toggle instead of
    leaving the user at a dead end. When `low_balance`, a green Top-up
    shortcut sits next to Buy so the user can fund the purchase right here.
    """
    kb = InlineKeyboardBuilder()
    if not out_of_stock:
        if low_balance:
            kb.row(
                cbtn(localize("btn.buy"), "buy_item", color=PRIMARY, icon="buy"),
                cbtn(localize("btn.replenish"), "replenish_balance", color=SUCCESS, icon="usdt"),
            )
        else:
            kb.row(cbtn(localize("btn.buy"), "buy_item", color=SUCCESS, icon="buy"))
    kb.row(cbtn(localize("btn.add_to_cart"), "add_to_cart", color=PRIMARY, icon="cart"))
    if applied_promo:
        kb.row(cbtn(localize("btn.remove_promo"), "remove_promo", color=DANGER, icon="minus"))
    else:
        kb.row(cbtn(localize("btn.apply_promo"), "apply_promo", color=PRIMARY, icon="copy"))
    if reviews_enabled:
        if review_count > 0:
            kb.row(cbtn(localize("btn.view_reviews", count=review_count), "reviews:0",
                        color=PRIMARY, icon="list"))
        if has_purchased:
            kb.row(cbtn(localize("btn.leave_review"), "review", color=PRIMARY, icon="star"))
    if out_of_stock:
        if subscribed:
            kb.row(cbtn(localize("btn.notify_stock_off"), "unsub_stock", color=DANGER, icon="minus"))
        else:
            kb.row(cbtn(localize("btn.notify_stock"), "sub_stock", color=SUCCESS, icon="fire"))
    kb.row(cbtn(localize("btn.back"), back_data, color=PRIMARY, icon="back"))
    return kb.as_markup()


def cart_keyboard(items: list[dict]) -> InlineKeyboardMarkup:
    """
    Cart view — aesthetic: quantity steppers, blue utility rows, green checkout.
    """
    kb = InlineKeyboardBuilder()
    for item in items:
        kb.row(
            cbtn("➖", f"cart_qty:{item['id']}:-1", color=DANGER, icon="minus"),
            InlineKeyboardButton(
                text=clean_label(f"{item['item_name']} ×{item['quantity']}"),
                callback_data="dummy_button",
                style=PRIMARY,
            ),
            cbtn("➕", f"cart_qty:{item['id']}:1", color=SUCCESS, icon="plus"),
        )
        if item.get('promo_code'):
            kb.row(cbtn(
                localize("btn.cart_remove_promo", code=item['promo_code']),
                f"cart_unpromo:{item['id']}",
                color=DANGER, icon="minus",
            ))
        kb.row(cbtn(
            localize("btn.cart_remove_item", name=item['item_name']),
            f"cart_remove:{item['id']}",
            color=DANGER, icon="trash",
        ))
    kb.row(cbtn(localize("btn.cart_checkout"), "cart_checkout", color=SUCCESS, icon="buy"))
    kb.row(cbtn(localize("btn.cart_clear"), "cart_clear", color=DANGER, icon="trash"))
    kb.row(cbtn(localize("btn.back"), "profile", color=PRIMARY, icon="back"))
    return kb.as_markup()


def payment_menu(pay_url: str) -> InlineKeyboardMarkup:
    """
    Buttons under the invoice (CryptoPay, etc.).
    """
    kb = InlineKeyboardBuilder()
    kb.row(cbtn(localize("btn.pay"), url=pay_url, color=SUCCESS, icon="usdt"))
    kb.row(cbtn(localize("btn.check_payment"), "check", color=PRIMARY, icon="history"))
    kb.row(cbtn(localize("btn.back"), "profile", color=DANGER, icon="back"))
    return kb.as_markup()


def get_payment_choice() -> InlineKeyboardMarkup:
    """
    Select a payment method — UPI (INR) first when configured, then Stars,
    then CryptoPay; Telegram Payments only when a provider token exists.
    """
    from bot.misc import EnvKeys as _E
    kb = InlineKeyboardBuilder()
    if _E.UPI_ID:
        kb.row(cbtn(localize("btn.pay.upi"), "pay_upi", color=SUCCESS, icon="usdt"))
    if _E.STARS_PER_VALUE > 0:
        kb.row(cbtn(localize("btn.pay.stars"), "pay_stars", color=PRIMARY, icon="star"))
    if _E.CRYPTO_PAY_TOKEN:
        kb.row(cbtn(localize("btn.pay.crypto"), "pay_cryptopay", color=PRIMARY, icon="usdt"))
    if _E.TELEGRAM_PROVIDER_TOKEN:
        kb.row(cbtn(localize("btn.pay.tg"), "pay_fiat", color=PRIMARY, icon="copy"))
    kb.row(cbtn(localize("btn.back"), "replenish_balance", color=PRIMARY, icon="back"))
    return kb.as_markup()


def question_buttons(question: str, back_data: str) -> InlineKeyboardMarkup:
    """
    Universal confirm dialog — green Yes, red No, blue Back.
    """
    kb = InlineKeyboardBuilder()
    kb.row(cbtn(localize("btn.yes"), f"{question}_yes", color=SUCCESS, icon="buy"))
    kb.row(cbtn(localize("btn.no"), f"{question}_no", color=DANGER, icon="minus"))
    kb.row(cbtn(localize("btn.back"), back_data, color=PRIMARY, icon="back"))
    return kb.as_markup()


def check_sub(channel_username: str) -> InlineKeyboardMarkup:
    """
    checks the channel subscription — EagleX gate style: green Join + green Check.
    """
    kb = InlineKeyboardBuilder()
    kb.row(cbtn(localize("btn.channel"), url=f"https://t.me/{channel_username}", color=SUCCESS, icon="share"))
    kb.row(cbtn(localize("btn.check_subscription"), "sub_channel_done", color=SUCCESS, icon="buy"))
    return kb.as_markup()


def rating_keyboard() -> InlineKeyboardMarkup:
    """Rating selection keyboard (1-5 stars)."""
    kb = InlineKeyboardBuilder()
    for i in range(1, 6):
        kb.button(text="★" * i, callback_data=f"rating:{i}", style=SUCCESS if i >= 4 else PRIMARY)
    kb.button(text=clean_label(localize("btn.back")), callback_data="back_to_menu", style=PRIMARY)
    kb.adjust(5)
    return kb.as_markup()


def referral_system_keyboard(has_referrals: bool = False, has_earnings: bool = False) -> InlineKeyboardMarkup:
    """Invite & Earn page: Share link, Copy link, (lists), Back."""
    kb = InlineKeyboardBuilder()
    kb.row(
        cbtn(localize("btn.share_link"), "ref_share", color=SUCCESS, icon="share"),
        cbtn(localize("btn.copy_link"), "ref_copy", color=PRIMARY, icon="copy"),
    )
    if has_referrals:
        kb.row(cbtn(localize("btn.view_referrals"), "view_referrals", color=PRIMARY, icon="users"))
    if has_earnings:
        kb.row(cbtn(localize("btn.view_earnings"), "view_all_earnings", color=PRIMARY, icon="usdt"))
    kb.row(cbtn(localize("btn.back"), "back_to_menu", color=PRIMARY, icon="back"))
    return kb.as_markup()


def help_keyboard() -> InlineKeyboardMarkup:
    """Help section: quick jumps + support + back."""
    kb = InlineKeyboardBuilder()
    kb.row(cbtn(localize("btn.help.how_buy"), "shop", color=PRIMARY, icon="shop"))
    kb.row(cbtn(localize("btn.help.topup"), "replenish_balance", color=PRIMARY, icon="usdt"))
    kb.row(cbtn(localize("btn.help.policy"), "rules", color=PRIMARY, icon="policy"))
    kb.row(cbtn(localize("btn.back"), "back_to_menu", color=PRIMARY, icon="back"))
    return kb.as_markup()


def language_keyboard(current: str = "en") -> InlineKeyboardMarkup:
    """Locale picker with a check on the active language."""
    from bot.i18n.strings import TRANSLATIONS
    names = {"en": "English", "ru": "Русский", "hi": "हिन्दी"}
    kb = InlineKeyboardBuilder()
    for code in TRANSLATIONS.keys():
        label = names.get(code, code)
        if code == current:
            label = f"✓ {label}"
        kb.row(cbtn(label, f"set_lang:{code}", color=PRIMARY, icon="language"))
    kb.row(cbtn(localize("btn.back"), "back_to_menu", color=PRIMARY, icon="back"))
    return kb.as_markup()


def force_channels_admin_kb(channels: list[dict]) -> InlineKeyboardMarkup:
    """Admin: list of gate channels with toggle/remove + add + back."""
    kb = InlineKeyboardBuilder()
    for ch in channels:
        label = (ch.get("title") or ch.get("username") or ch["chat_id"])
        state_icon = "minus" if ch["is_active"] else "plus"
        kb.row(
            cbtn(label, "dummy_button", color=PRIMARY, icon="share"),
            cbtn("⏻", f"fc_toggle:{ch['chat_id']}", color=PRIMARY, icon=state_icon),
            cbtn("✕", f"fc_del:{ch['chat_id']}", color=DANGER, icon="trash"),
        )
    kb.row(cbtn(localize("admin.fc.add"), "fc_add", color=SUCCESS, icon="plus"))
    kb.row(cbtn(localize("btn.back"), "console", color=PRIMARY, icon="back"))
    return kb.as_markup()
