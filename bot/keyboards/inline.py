from typing import Callable, Iterable, Tuple
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from bot.i18n import localize
from bot.database.models import Permission
from bot.misc import LazyPaginator # noqa: F401
from bot.ui import SUCCESS, PRIMARY, DANGER, ICON, btn


def header(title: str, subtitle: str = "") -> str:
    """Aesthetic screen header — diamond accent + thin rule (our own look)."""
    lines = [f"◇ {title}", "─────────────"]
    if subtitle:
        lines.append(subtitle)
    return "\n".join(lines)

def main_menu(role: int, channel: str | None = None, helper: str | None = None) -> InlineKeyboardMarkup:
    """
    Main menu — EagleX style: green shop CTA, blue navigation, red admin.
    """
    kb = InlineKeyboardBuilder()
    kb.button(text=localize("btn.shop"), callback_data="shop",
              style=SUCCESS, icon_custom_emoji_id=ICON["shop"])
    kb.button(text=localize("btn.profile"), callback_data="profile",
              style=PRIMARY, icon_custom_emoji_id=ICON["wallet"])
    kb.button(text=localize("btn.rules"), callback_data="rules",
              style=PRIMARY, icon_custom_emoji_id=ICON["policy"])
    if helper:
        kb.button(text=localize("btn.support"), url=f"tg://user?id={helper}",
                  style=PRIMARY, icon_custom_emoji_id=ICON["help"])
    if channel:
        kb.button(text=localize("btn.channel"), url=f"https://t.me/{channel.lstrip('@')}",
                  style=PRIMARY, icon_custom_emoji_id=ICON["share"])
    if Permission.has_any_admin_perm(role):
        kb.button(text=localize("btn.admin_menu"), callback_data="console",
                  style=DANGER, icon_custom_emoji_id=ICON["star"])
    kb.adjust(1)
    return kb.as_markup()


def profile_keyboard(referral_percent: int, user_items: int = 0, cart_count: int = 0) -> InlineKeyboardMarkup:
    """
    Profile keyboard — wallet-style: green top-up, blue navigation, red back.
    """
    kb = InlineKeyboardBuilder()
    kb.button(text=localize("btn.replenish"), callback_data="replenish_balance",
              style=SUCCESS, icon_custom_emoji_id=ICON["usdt"])
    if referral_percent != 0:
        kb.button(text=localize("btn.referral"), callback_data="referral_system",
                  style=PRIMARY, icon_custom_emoji_id=ICON["invite"])
    if user_items != 0:
        kb.button(text=localize("btn.purchased"), callback_data="bought_items",
                  style=PRIMARY, icon_custom_emoji_id=ICON["buy"])
    cart_text = localize("btn.cart", count=cart_count) if cart_count > 0 else localize("btn.cart_empty")
    kb.button(text=cart_text, callback_data="cart",
              style=PRIMARY, icon_custom_emoji_id=ICON["shop"])
    kb.button(text=localize("btn.operation_history"), callback_data="operation_history",
              style=PRIMARY, icon_custom_emoji_id=ICON["history"])
    kb.button(text=localize("btn.redeem_promo"), callback_data="redeem_promo",
              style=PRIMARY, icon_custom_emoji_id=ICON["copy"])
    kb.button(text=localize("btn.back"), callback_data="back_to_menu",
              style=DANGER, icon_custom_emoji_id=ICON["back"])
    kb.adjust(1)
    return kb.as_markup()


def admin_console_keyboard(maintenance_mode: bool = False, role: int = 127) -> InlineKeyboardMarkup:
    """
    Admin panel — shows only buttons the user has permissions for.
    """
    kb = InlineKeyboardBuilder()
    if role & Permission.CATALOG_MANAGE:
        kb.button(text=localize("admin.menu.shop"), callback_data="shop_management",
                  style=PRIMARY, icon_custom_emoji_id=ICON["shop"])
        kb.button(text=localize("admin.menu.goods"), callback_data="goods_management",
                  style=PRIMARY, icon_custom_emoji_id=ICON["box"])
        kb.button(text=localize("admin.menu.categories"), callback_data="categories_management",
                  style=PRIMARY, icon_custom_emoji_id=ICON["pencil"])
    if role & Permission.PROMO_MANAGE:
        kb.button(text=localize("admin.menu.promo"), callback_data="promo_mgmt",
                  style=PRIMARY, icon_custom_emoji_id=ICON["star"])
    if role & Permission.USERS_MANAGE:
        kb.button(text=localize("admin.menu.users"), callback_data="user_management",
                  style=PRIMARY, icon_custom_emoji_id=ICON["wallet"])
    if role & Permission.ADMINS_MANAGE:
        kb.button(text=localize("admin.menu.roles"), callback_data="role_mgmt",
                  style=PRIMARY, icon_custom_emoji_id=ICON["leaderboard"])
    if role & Permission.BROADCAST:
        kb.button(text=localize("admin.menu.broadcast"), callback_data="send_message",
                  style=PRIMARY, icon_custom_emoji_id=ICON["share"])
    if role & Permission.SETTINGS_MANAGE:
        maintenance_key = "admin.menu.maintenance_on" if maintenance_mode else "admin.menu.maintenance_off"
        kb.button(text=localize(maintenance_key), callback_data="toggle_maintenance",
                  style=DANGER, icon_custom_emoji_id=ICON["help"])
    kb.button(text=localize("btn.back"), callback_data="back_to_menu",
              style=DANGER, icon_custom_emoji_id=ICON["back"])
    kb.adjust(1)
    return kb.as_markup()


def simple_buttons(buttons: Iterable[Tuple[str, str]], per_row: int = 1) -> InlineKeyboardMarkup:
    """
    Universal button assembly from (text, callback_data) — default blue look.
    """
    kb = InlineKeyboardBuilder()
    for text, cb in buttons:
        kb.button(text=text, callback_data=cb, style=PRIMARY)
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
    One button 'Close'.
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
            nav_buttons.append(InlineKeyboardButton(text="◀️", callback_data=f"{nav_cb_prefix}{page - 1}"))
        nav_buttons.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="dummy_button"))
        if page < total_pages - 1:
            nav_buttons.append(InlineKeyboardButton(text="▶️", callback_data=f"{nav_cb_prefix}{page + 1}"))
        kb.row(*nav_buttons)

    if back_cb:
        kb.row(InlineKeyboardButton(text=back_text or localize("btn.back"), callback_data=back_cb))

    return kb.as_markup()


def item_info(
        back_data: str, avg_rating: float = None,
        review_count: int = 0, has_purchased: bool = False,
        applied_promo: str = None, reviews_enabled: bool = True,
        out_of_stock: bool = False, subscribed: bool = False,
) -> InlineKeyboardMarkup:
    """
    Product card — EagleX style: green Buy, blue extras, red Back.

    When `out_of_stock`, offers a restock notification toggle instead of
    leaving the user at a dead end.
    """
    kb = InlineKeyboardBuilder()
    if not out_of_stock:
        kb.button(text=localize("btn.buy"), callback_data="buy_item",
                  style=SUCCESS, icon_custom_emoji_id=ICON["buy"])
    kb.button(text=localize("btn.add_to_cart"), callback_data="add_to_cart",
              style=PRIMARY, icon_custom_emoji_id=ICON["shop"])
    if applied_promo:
        kb.button(text=localize("btn.remove_promo"), callback_data="remove_promo",
                  style=DANGER, icon_custom_emoji_id=ICON["back"])
    else:
        kb.button(text=localize("btn.apply_promo"), callback_data="apply_promo",
                  style=PRIMARY, icon_custom_emoji_id=ICON["copy"])
    if reviews_enabled:
        if review_count > 0:
            kb.button(text=localize("btn.view_reviews", count=review_count), callback_data="reviews:0",
                      style=PRIMARY, icon_custom_emoji_id=ICON["history"])
        if has_purchased:
            kb.button(text=localize("btn.leave_review"), callback_data="review",
                      style=PRIMARY, icon_custom_emoji_id=ICON["star"])
    if out_of_stock:
        if subscribed:
            kb.button(text=localize("btn.notify_stock_off"), callback_data="unsub_stock",
                      style=DANGER, icon_custom_emoji_id=ICON["back"])
        else:
            kb.button(text=localize("btn.notify_stock"), callback_data="sub_stock",
                      style=SUCCESS, icon_custom_emoji_id=ICON["buy"])
    kb.button(text=localize("btn.back"), callback_data=back_data,
              style=DANGER, icon_custom_emoji_id=ICON["back"])
    kb.adjust(2)
    return kb.as_markup()


def cart_keyboard(items: list[dict]) -> InlineKeyboardMarkup:
    """
    Cart view — aesthetic: quantity steppers, blue utility rows, green checkout.
    """
    kb = InlineKeyboardBuilder()
    for item in items:
        kb.row(
            InlineKeyboardButton(text="➖", callback_data=f"cart_qty:{item['id']}:-1",
                                 style=DANGER, icon_custom_emoji_id=ICON["back"]),
            InlineKeyboardButton(
                text=f"{item['item_name']} ×{item['quantity']}",
                callback_data="dummy_button",
                style=PRIMARY,
            ),
            InlineKeyboardButton(text="➕", callback_data=f"cart_qty:{item['id']}:1",
                                 style=SUCCESS, icon_custom_emoji_id=ICON["buy"]),
        )
        if item.get('promo_code'):
            kb.row(InlineKeyboardButton(
                text=localize("btn.cart_remove_promo", code=item['promo_code']),
                callback_data=f"cart_unpromo:{item['id']}",
                style=DANGER, icon_custom_emoji_id=ICON["back"],
            ))
        kb.row(InlineKeyboardButton(
            text=localize("btn.cart_remove_item", name=item['item_name']),
            callback_data=f"cart_remove:{item['id']}",
            style=DANGER, icon_custom_emoji_id=ICON["back"],
        ))
    kb.button(text=localize("btn.cart_checkout"), callback_data="cart_checkout",
              style=SUCCESS, icon_custom_emoji_id=ICON["buy"])
    kb.button(text=localize("btn.cart_clear"), callback_data="cart_clear",
              style=DANGER, icon_custom_emoji_id=ICON["cart"])
    kb.button(text=localize("btn.back"), callback_data="profile",
              style=PRIMARY, icon_custom_emoji_id=ICON["back"])
    kb.adjust(1)
    return kb.as_markup()


def payment_menu(pay_url: str) -> InlineKeyboardMarkup:
    """
    Buttons under the invoice (CryptoPay, etc.).
    """
    kb = InlineKeyboardBuilder()
    kb.button(text=localize("btn.pay"), url=pay_url,
              style=SUCCESS, icon_custom_emoji_id=ICON["usdt"])
    kb.button(text=localize("btn.check_payment"), callback_data="check",
              style=PRIMARY, icon_custom_emoji_id=ICON["history"])
    kb.button(text=localize("btn.back"), callback_data="profile",
              style=DANGER, icon_custom_emoji_id=ICON["back"])
    kb.adjust(1)
    return kb.as_markup()


def get_payment_choice() -> InlineKeyboardMarkup:
    """
    Select a payment method.
    """
    kb = InlineKeyboardBuilder()
    kb.button(text=localize("btn.pay.crypto"), callback_data="pay_cryptopay",
              style=SUCCESS, icon_custom_emoji_id=ICON["usdt"])
    kb.button(text=localize("btn.pay.stars"), callback_data="pay_stars",
              style=PRIMARY, icon_custom_emoji_id=ICON["star"])
    kb.button(text=localize("btn.pay.tg"), callback_data="pay_fiat",
              style=PRIMARY, icon_custom_emoji_id=ICON["copy"])
    kb.button(text=localize("btn.back"), callback_data="replenish_balance",
              style=DANGER, icon_custom_emoji_id=ICON["back"])
    kb.adjust(1)
    return kb.as_markup()


def question_buttons(question: str, back_data: str) -> InlineKeyboardMarkup:
    """
    Universal confirm dialog — green Yes, red No, blue Back.
    """
    kb = InlineKeyboardBuilder()
    kb.button(text=localize("btn.yes"), callback_data=f"{question}_yes",
              style=SUCCESS, icon_custom_emoji_id=ICON["buy"])
    kb.button(text=localize("btn.no"), callback_data=f"{question}_no",
              style=DANGER, icon_custom_emoji_id=ICON["back"])
    kb.button(text=localize("btn.back"), callback_data=back_data,
              style=PRIMARY, icon_custom_emoji_id=ICON["back"])
    kb.adjust(2)
    return kb.as_markup()


def check_sub(channel_username: str) -> InlineKeyboardMarkup:
    """
    checks the channel subscription — EagleX gate style: green Join + green Check.
    """
    kb = InlineKeyboardBuilder()
    kb.button(text=localize("btn.channel"), url=f"https://t.me/{channel_username}",
              style=SUCCESS, icon_custom_emoji_id=ICON["share"])
    kb.button(text=localize("btn.check_subscription"), callback_data="sub_channel_done",
              style=SUCCESS, icon_custom_emoji_id=ICON["buy"])
    kb.adjust(1)
    return kb.as_markup()


def rating_keyboard() -> InlineKeyboardMarkup:
    """Rating selection keyboard (1-5 stars)."""
    kb = InlineKeyboardBuilder()
    for i in range(1, 6):
        kb.button(text="⭐" * i, callback_data=f"rating:{i}")
    kb.button(text=localize("btn.back"), callback_data="back_to_menu")
    kb.adjust(5)
    return kb.as_markup()


def referral_system_keyboard(has_referrals: bool = False, has_earnings: bool = False) -> InlineKeyboardMarkup:
    """
    Referral system keyboard with additional buttons.
    """
    kb = InlineKeyboardBuilder()

    if has_referrals:
        kb.button(text=localize("btn.view_referrals"), callback_data="view_referrals",
                  style=PRIMARY, icon_custom_emoji_id=ICON["invite"])

    if has_earnings:
        kb.button(text=localize("btn.view_earnings"), callback_data="view_all_earnings",
                  style=PRIMARY, icon_custom_emoji_id=ICON["usdt"])

    kb.button(text=localize("btn.back"), callback_data="profile",
              style=DANGER, icon_custom_emoji_id=ICON["back"])
    kb.adjust(1)
    return kb.as_markup()
