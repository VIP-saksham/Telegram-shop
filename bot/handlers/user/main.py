# =============================================================================
#  Copyright (c) 2026 Saksham Swaroop (@truenakshu)  |  GitHub: VIP-saksham
#  LinkedIn: sakshamswaroop
#
#  All rights reserved. This source code is the private property of the
#  author. Copying, modifying, redistributing or deploying any part of this
#  file WITHOUT the author's written permission is strictly prohibited.
#  For licensing / permission: https://t.me/truenakshu
# =============================================================================

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.enums.chat_type import ChatType
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

import asyncio
import datetime
from html import escape as _esc

from bot.database.methods import (
    select_max_role_id, create_user, check_role_cached, check_user,
    select_user_operations_total, select_user_items, check_user_cached,
    get_role_id_by_name
)
from bot.database.models import Permission
from bot.database.methods.read import get_cart_count, invalidate_user_cache
from bot.database.methods.lazy_queries import query_user_operations_history
from bot.handlers.other import check_sub_channel, _parse_channel_username
from bot.handlers.user.entry_gate import run_gate
from bot.keyboards import main_menu, back, profile_keyboard, check_sub
from bot.misc import EnvKeys
from bot.ui import banner, quote
from bot.misc.metrics import get_metrics
from bot.i18n import localize
from bot.logger_mesh import logger

router = Router()


async def _ensure_user(user_id: int) -> dict | None:
    """Return the user's row, registering them first if it is missing.

    A stale keyboard (or a wiped database) can hand a callback from someone
    with no row at all; every screen that reads user fields needs the row to
    exist rather than blowing up on None.
    """
    user = await check_user_cached(user_id)
    if user:
        return user

    await create_user(
        telegram_id=user_id,
        registration_date=datetime.datetime.now(datetime.timezone.utc),
        referral_id=None,
        role=1,
    )
    await invalidate_user_cache(user_id)
    return await check_user_cached(user_id)


def _channel_chat_id(channel_username: str) -> int | str:
    """Resolve the chat id to query for the subscription check.

    CHANNEL_ID wins when set (private channels have no username to address), but
    a non-numeric value in the env must not take the handler down with it.
    """
    raw = EnvKeys.CHANNEL_ID
    if raw:
        try:
            return int(raw)
        except (TypeError, ValueError):
            logger.warning("CHANNEL_ID=%r is not a valid chat id; falling back to @%s", raw, channel_username)
    return f"@{channel_username}"


async def _bot_display_name(bot) -> str:
    """The bot's display name for the banner, with a safe fallback.

    Tolerates failed getMe calls and non-string attributes so the start
    screen never goes down over cosmetics.
    """
    try:
        me = await bot.me()
    except Exception:  # noqa: BLE001 — cosmetics must never block /start
        return "shop"
    name = getattr(me, "first_name", None)
    return name if isinstance(name, str) and name.strip() else "shop"


async def _delete_quietly(message: Message) -> None:
    """Delete a message, tolerating the cases Telegram refuses.

    A message older than 48h, or one in a chat where the bot lost delete rights,
    raises — and that must not abort a handler that already did its real work.
    """
    try:
        await message.delete()
    except (TelegramBadRequest, TelegramForbiddenError) as e:
        logger.debug(f"Failed to delete message: {e}")


async def _is_subscribed(bot, channel_username: str, user_id: int) -> bool | None:
    """Whether the user is in the required channel.

    Returns None when the check could not be performed (private channel, bad
    link, bot not an admin) so callers can treat it as "don't block".
    """
    try:
        chat_member = await bot.get_chat_member(
            chat_id=_channel_chat_id(channel_username), user_id=user_id
        )
    except (TelegramBadRequest, TelegramForbiddenError) as e:
        logger.warning(f"Channel subscription check failed for user {user_id}: {e}")
        return None
    return await check_sub_channel(chat_member)


@router.message(F.text.startswith('/redeem'))
async def redeem_command(message: Message, state: FSMContext):
    """/redeem — jump straight to the promo-code entry."""
    if message.chat.type != ChatType.PRIVATE:
        return
    await state.clear()
    from bot.states import PromoFSM
    from bot.keyboards import back
    await message.answer(localize("promo.enter_redeem_code"), reply_markup=back("back_to_menu"))
    await state.set_state(PromoFSM.waiting_redeem_code)


@router.message(F.text.startswith('/help'))
async def help_command(message: Message, state: FSMContext):
    """/help — open the Help tab."""
    if message.chat.type != ChatType.PRIVATE:
        return
    await state.clear()
    from bot.ui import banner, quote
    from bot.keyboards import help_keyboard
    text = "\n".join([
        banner(localize("help.title")),
        "",
        localize("help.body"),
        "",
        quote(localize("help.tip")),
    ])
    await message.answer(text, reply_markup=help_keyboard())


@router.message(F.text.startswith('/ac'))
async def ac_command(message: Message, state: FSMContext):
    """/ac — admin panel shortcut (permission-checked)."""
    if message.chat.type != ChatType.PRIVATE:
        return
    await state.clear()

    role = await check_role_cached(message.from_user.id) or 0
    if not Permission.has_any_admin_perm(role):
        await message.answer(localize("admin.menu.rights"))
        return

    from bot.keyboards import admin_console_keyboard
    from bot.middleware.security import get_auth_middleware
    mw = get_auth_middleware()
    maintenance = mw.maintenance_mode if mw else False
    await message.answer(
        localize("admin.menu.main"),
        reply_markup=admin_console_keyboard(maintenance_mode=maintenance, role=role),
    )


@router.message(F.text.startswith('/start'))
async def start(message: Message, state: FSMContext):
    """
    Handle /start:
    - Ensure user exists (register if new)
    - (Optional) Check channel subscription
    - Show the main menu
    """
    if message.chat.type != ChatType.PRIVATE:
        return

    user_id = message.from_user.id
    await state.clear()

    role_data = await check_role_cached(user_id)

    if role_data == 0:
        owner_max_role = await select_max_role_id()
        if user_id == EnvKeys.OWNER_ID:
            # The OWNER from env gets the highest role in the database.
            user_role = owner_max_role
        elif EnvKeys.is_sudo(user_id):
            # Sudo users get the built-in SUDO role (full control, below OWNER).
            sudo_role_id = await get_role_id_by_name('SUDO')
            user_role = sudo_role_id or owner_max_role
        else:
            user_role = 1

        referral_id = None
        parts = message.text.split(maxsplit=1)
        if len(parts) > 1:
            payload = parts[1].strip()
            if payload.isdigit() and payload != str(user_id):
                candidate = int(payload)
                if await check_user(candidate) is not None:
                    referral_id = candidate

        # registration_date is DateTime
        await create_user(
            telegram_id=int(user_id),
            registration_date=datetime.datetime.now(datetime.timezone.utc),
            referral_id=referral_id,
            role=user_role
        )

        await invalidate_user_cache(user_id)
        from bot.middleware.security import invalidate_auth_caches
        invalidate_auth_caches(user_id)

        metrics = get_metrics()
        if metrics:
            metrics.track_event("registration", user_id)

        # Re-read (now cached) so the menu reflects the freshly assigned role.
        role_data = await check_role_cached(user_id)

    channel_username = _parse_channel_username()

    # Every /start lands in the general log group (not just money events).
    # Logged BEFORE the gate so even force-join drop-offs are visible.
    from bot.database.methods.audit import log_audit_bg
    log_audit_bg(
        "user_start", user_id=user_id,
        resource_type="User", resource_id=user_id,
        details=f"start from @{message.from_user.username or message.from_user.first_name}",
    )

    # Entry gate: force-join channels -> captcha (every start) -> menu.
    if not await run_gate(message, state, captcha=True):
        await _delete_quietly(message)
        return

    markup = main_menu(role=role_data, channel=channel_username, helper=EnvKeys.HELPER_ID)

    text = f"{banner(bot_name, localize('menu.hello', name=_esc(message.from_user.first_name or '')))}\n\n" \
        f"{localize('menu.start', name=bot_name)}"
    await message.answer(text, reply_markup=markup)
    await _delete_quietly(message)
    await state.clear()


@router.callback_query(F.data == "back_to_menu")
async def back_to_menu_callback_handler(call: CallbackQuery, state: FSMContext):
    """
    Return user to the main menu.
    """
    user_id = call.from_user.id
    await _ensure_user(user_id)

    role = await check_role_cached(user_id) or 0

    channel_username = _parse_channel_username()

    # Menu returns re-check the force-join but skip the captcha — the puzzle
    # runs on every /start, not on navigation.
    if not await run_gate(call, state, captcha=False):
        return

    markup = main_menu(role=role, channel=channel_username, helper=EnvKeys.HELPER_ID)
    bot_name = await _bot_display_name(call.bot)
    text = f"{banner(bot_name, localize('menu.hello', name=_esc(call.from_user.first_name or '')))}\n\n" \
        f"{localize('menu.start', name=bot_name)}"
    await call.message.edit_text(text, reply_markup=markup)
    await state.clear()


@router.callback_query(F.data == "rules")
async def rules_callback_handler(call: CallbackQuery, state: FSMContext):
    """
    Show the Bot Policy (env RULES wins when the admin set custom text).
    """
    rules_data = EnvKeys.RULES
    body = rules_data or localize("policy.body")
    text = f"{banner(localize('policy.title'))}\n\n{body}"
    await call.message.edit_text(text, reply_markup=back("back_to_menu"), parse_mode="HTML")
    await state.clear()


@router.callback_query(F.data == "help_menu")
async def help_menu_handler(call: CallbackQuery, state: FSMContext):
    """Help section: quick how-to + jumps."""
    text = "\n".join([
        banner(localize("help.title")),
        "",
        localize("help.body"),
        "",
        quote(localize("help.tip")),
    ])
    from bot.keyboards import help_keyboard
    await call.message.edit_text(text, reply_markup=help_keyboard())
    await state.clear()


@router.callback_query(F.data == "change_language")
async def change_language_handler(call: CallbackQuery, state: FSMContext):
    """Language picker."""
    from bot.keyboards import language_keyboard
    from bot.i18n.main import get_locale
    text = f"{banner(localize('language.title'))}"
    await call.message.edit_text(text, reply_markup=language_keyboard(get_locale()))
    await state.clear()


@router.callback_query(F.data.startswith("set_lang:"))
async def set_language_handler(call: CallbackQuery, state: FSMContext):
    """Store the language choice per chat and re-open the menu in it.

    Locale lives in Redis-backed FSM storage keyed by chat, so it survives
    restarts with Redis and falls back to BOT_LOCALE without it.
    """
    code = call.data.split(":", 1)[1]
    from bot.i18n.strings import TRANSLATIONS
    if code not in TRANSLATIONS:
        await call.answer(localize("errors.invalid_data"), show_alert=True)
        return

    await state.update_data(locale=code)
    from bot.i18n import main as i18n_main
    i18n_main.set_chat_locale(call.message.chat.id, code)
    # Re-bind for the rest of this update's context (menu render below).

    names = {"en": "English", "ru": "Русский", "hi": "हिन्दी"}
    await call.answer(localize("language.set", lang=names.get(code, code)))

    # Re-open the menu in the chosen language.
    user_id = call.from_user.id
    await _ensure_user(user_id)
    role = await check_role_cached(user_id) or 0
    from bot.handlers.user.entry_gate import _open_menu
    await _open_menu(call, state)


@router.callback_query(F.data == "profile")
async def profile_callback_handler(call: CallbackQuery, state: FSMContext):
    """
    Send profile info (balance, purchases count, id, etc.).
    """
    user_id = call.from_user.id
    tg_user = call.from_user
    user_info = await _ensure_user(user_id)
    if not user_info:
        await call.answer(localize("errors.something_wrong"), show_alert=True)
        return

    balance = user_info.get('balance')
    overall_balance, items, cart_count = await asyncio.gather(
        select_user_operations_total(user_id),
        select_user_items(user_id),
        get_cart_count(user_id),
    )
    referral = EnvKeys.REFERRAL_PERCENT

    markup = profile_keyboard(referral, items, cart_count=cart_count)
    text = "\n".join([
        banner(localize("profile.title"), localize("profile.caption", name=_esc(tg_user.first_name or ''), id=user_id)),
        localize("profile.id", id=user_id),
        localize("profile.balance", amount=balance, currency=EnvKeys.PAY_CURRENCY),
        localize("profile.total_topup", amount=overall_balance, currency=EnvKeys.PAY_CURRENCY),
        localize("profile.purchased_count", count=items),
        "",
        quote(localize("profile.tip")),
    ])
    try:
        await call.message.edit_text(text, reply_markup=markup, parse_mode='HTML')
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise
    await state.clear()


@router.callback_query(F.data == "sub_channel_done")
async def check_sub_to_channel(call: CallbackQuery, state: FSMContext):
    """
    Re-check channel subscription after user clicks "Check".
    """
    user_id = call.from_user.id
    channel_username = _parse_channel_username()
    helper = EnvKeys.HELPER_ID

    if channel_username:
        # None (check unavailable) is treated as subscribed, matching /start: a misconfigured channel must not lock everyone out of the bot.
        if await _is_subscribed(call.bot, channel_username, user_id) is not False:
            await _ensure_user(user_id)
            role = await check_role_cached(user_id) or 0
            markup = main_menu(role, channel_username, helper)
            bot_name = await _bot_display_name(call.bot)
            text = f"{banner(bot_name, localize('menu.hello', name=_esc(call.from_user.first_name or '')))}\n\n" \
                f"{localize('menu.start', name=bot_name)}"
            await call.message.edit_text(text, reply_markup=markup)
            await state.clear()
            return

    await call.answer(localize("errors.not_subscribed"))


# --- Operation History ---

@router.callback_query(F.data == "operation_history")
async def operation_history_handler(call: CallbackQuery, state: FSMContext):
    """History hub: Payments / Your products / Coupon history."""
    from bot.ui import banner, quote, cbtn, SUCCESS, PRIMARY, DANGER
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    kb = InlineKeyboardBuilder()
    kb.row(cbtn(localize("history.btn.payments"), "history_payments", color=SUCCESS, icon="usdt"))
    kb.row(cbtn(localize("history.btn.products"), "bought_items", color=PRIMARY, icon="box"))
    kb.row(cbtn(localize("history.btn.coupons"), "history_coupons", color=PRIMARY, icon="star"))
    kb.row(cbtn(localize("btn.back"), "profile", color=DANGER, icon="back"))

    text = f"{banner(localize('history.title'))}\n\n{quote(localize('history.hub_hint'))}"
    await call.message.edit_text(text, reply_markup=kb.as_markup())
    await state.clear()


@router.callback_query(F.data == "history_payments")
async def history_payments_handler(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    await _show_operations_page(call, state, user_id, 0)


@router.callback_query(F.data == "history_coupons")
async def history_coupons_handler(call: CallbackQuery, state: FSMContext):
    """Coupon (promo) redemption history for this user."""
    from bot.ui import banner, quote
    from bot.database.methods.read import get_user_promo_redemptions

    rows = await get_user_promo_redemptions(call.from_user.id)
    lines = [banner(localize("history.coupons.title")), ""]
    if not rows:
        lines.append(localize("history.coupons.empty"))
    else:
        for r in rows:
            lines.append(localize("history.coupons.row", code=r["code"], amount=r["amount"],
                                  currency=EnvKeys.PAY_CURRENCY, date=str(r["date"])[:16]))

    from bot.keyboards import back
    await call.message.edit_text("\n".join(lines), reply_markup=back("operation_history"))
    await state.clear()


@router.callback_query(F.data.startswith("ops-page_"))
async def navigate_operations(call: CallbackQuery, state: FSMContext):
    try:
        page = int(call.data.split("_")[1])
    except (ValueError, IndexError):
        await call.answer(localize("errors.pagination_invalid"))
        return
    await _show_operations_page(call, state, call.from_user.id, page)


async def _show_operations_page(call: CallbackQuery, state: FSMContext, user_id: int, page: int):
    from functools import partial
    from bot.misc import LazyPaginator

    paginator = LazyPaginator(partial(query_user_operations_history, user_id), per_page=10)
    items = await paginator.get_page(page)
    total_pages = await paginator.get_total_pages()

    if not items:
        await call.message.edit_text(
            f"{banner(localize('history.title'))}\n\n{quote(localize('history.empty'))}",
            reply_markup=back("profile"),
        )
        return

    lines = [banner(localize("history.title")), ""]
    for op in items:
        op_type = op['type']
        amount = op['amount']
        date = op['date']
        date_str = str(date)[:19] if date else ""

        if op_type == 'topup':
            lines.append(localize("history.topup", amount=amount, currency=EnvKeys.PAY_CURRENCY))
        elif op_type == 'purchase':
            lines.append(localize("history.purchase", amount=amount, currency=EnvKeys.PAY_CURRENCY))
        elif op_type == 'referral':
            lines.append(localize("history.referral", amount=amount, currency=EnvKeys.PAY_CURRENCY))
        lines.append(localize("history.date", date=date_str))
        lines.append("")

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    kb = InlineKeyboardBuilder()
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="◀️", callback_data=f"ops-page_{page - 1}"))
    if total_pages > 1:
        nav_buttons.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="dummy_button"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text="▶️", callback_data=f"ops-page_{page + 1}"))
    if nav_buttons:
        kb.row(*nav_buttons)
    kb.row(InlineKeyboardButton(text=localize("btn.back"), callback_data="profile"))

    await call.message.edit_text("\n".join(lines), reply_markup=kb.as_markup())


