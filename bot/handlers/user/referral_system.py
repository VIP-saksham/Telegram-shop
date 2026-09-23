from functools import partial

from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

from bot.database.methods import (
    check_user_referrals, get_referral_earnings_stats, get_one_referral_earning, query_user_referrals,
    query_referral_earnings_from_user, query_all_referral_earnings,
)
from bot.handlers.other import get_bot_info, display_name
from bot.keyboards import back, referral_system_keyboard, lazy_paginated_keyboard
from bot.misc import EnvKeys, LazyPaginator
from bot.i18n import localize, esc
from bot.ui import cbtn, PRIMARY, SUCCESS

router = Router()


@router.callback_query(F.data == "referral_system")
async def referral_callback_handler(call: CallbackQuery, state: FSMContext):
    """
    Invite & Earn page: reward, referral count, total earned, personal link.
    """
    from bot.ui import banner, quote, kv

    user_id = call.from_user.id
    referrals_count = await check_user_referrals(user_id)
    bot_username = await get_bot_info(call)
    earnings_stats = await get_referral_earnings_stats(user_id)

    has_referrals = referrals_count > 0
    has_earnings = earnings_stats['total_earnings_count'] > 0

    reward = EnvKeys.REFERRAL_REWARD
    text = "\n".join([
        banner(localize("invite.title")),
        "",
        localize("invite.desc"),
        "",
        kv(localize("invite.reward_key"), f"Rs.{reward}"),
        kv(localize("invite.count_key"), str(referrals_count)),
        kv(localize("invite.earned_key"), f"Rs.{earnings_stats['total_amount']}"),
        "",
        f"{localize('invite.link_label')}\n{localize('invite.link', bot_username=bot_username, user_id=user_id)}",
        "",
        quote(localize("invite.share_hint")),
    ])

    markup = referral_system_keyboard(has_referrals, has_earnings)
    await call.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
    await state.clear()


@router.callback_query(F.data == "ref_share")
async def ref_share_handler(call: CallbackQuery, state: FSMContext):
    """Open Telegram's native share prompt with the invite link."""
    user_id = call.from_user.id
    bot_username = await get_bot_info(call)
    link = f"https://t.me/{bot_username}?start={user_id}"
    url = f"https://t.me/share/url?url={link}&text={localize('invite.share_text')}"
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    kb.row(cbtn(localize("btn.share_link"), url=url, color=SUCCESS, icon="share"))
    kb.row(cbtn(localize("btn.back"), "referral_system", color=PRIMARY, icon="back"))
    await call.message.edit_text(localize("invite.share_hint"), reply_markup=kb.as_markup())
    await state.clear()


@router.callback_query(F.data == "ref_copy")
async def ref_copy_handler(call: CallbackQuery, state: FSMContext):
    """Show the link alone so the client's copy button is one tap away."""
    user_id = call.from_user.id
    bot_username = await get_bot_info(call)
    text = f"{localize('invite.link_label')}\n{localize('invite.link', bot_username=bot_username, user_id=user_id)}"
    await call.message.edit_text(text, reply_markup=back("referral_system"), parse_mode="HTML")
    await state.clear()


@router.callback_query(F.data == "ref_leaderboard")
async def ref_leaderboard_handler(call: CallbackQuery, state: FSMContext):
    """Top referrers with names, medal places for the podium."""
    from bot.database.methods.read import top_referrers
    from bot.ui import banner, quote

    rows = await top_referrers(limit=10)
    if not rows:
        text = f"{banner(localize('leaderboard.title'))}\n\n{quote(localize('leaderboard.empty'))}"
        await call.message.edit_text(text, reply_markup=back("back_to_menu"))
        await state.clear()
        return

    medals = {0: "🥇", 1: "🥈", 2: "🥉"}
    lines = [banner(localize("leaderboard.title")), ""]
    for i, row in enumerate(rows):
        name = esc(await display_name(call.message.bot, row["user_id"]))
        place = medals.get(i, f"{i + 1}.")
        lines.append(localize("leaderboard.row", place=place, name=name, count=row["count"]))

    await call.message.edit_text("\n".join(lines), reply_markup=back("back_to_menu"))
    await state.clear()


@router.callback_query(F.data == "view_referrals")
async def view_referrals_handler(call: CallbackQuery, state: FSMContext):
    """
    Show a list of all user referrals with lazy loading.
    """
    user_id = call.from_user.id

    # Create paginator
    query_func = partial(query_user_referrals, user_id)
    paginator = LazyPaginator(query_func, per_page=10)

    # Check if there are any referrals
    total = await paginator.get_total_count()
    if total == 0:
        await call.message.edit_text(
            localize("referrals.list.empty"),
            reply_markup=back("referral_system")
        )
        return

    markup = await lazy_paginated_keyboard(
        paginator=paginator,
        item_text=lambda referral_data: localize("referrals.item.format",
                                                 telegram_id=referral_data['telegram_id'],
                                                 total_earned=int(referral_data['total_earned']),
                                                 currency=EnvKeys.PAY_CURRENCY),
        item_callback=lambda referral_data: f"referral_earnings_{referral_data['telegram_id']}",
        page=0,
        back_cb="referral_system",
        nav_cb_prefix="referrals_page_"
    )

    await call.message.edit_text(
        localize("referrals.list.title"),
        reply_markup=markup
    )


@router.callback_query(F.data.startswith("referrals_page_"))
async def referrals_pagination_handler(call: CallbackQuery, state: FSMContext):
    """
    Pagination processing for the referral list with lazy loading.
    """
    try:
        page = int(call.data.split("_")[-1])
    except (ValueError, IndexError):
        await call.answer(localize("errors.pagination_invalid"))
        return

    user_id = call.from_user.id

    # Create paginator
    query_func = partial(query_user_referrals, user_id)
    paginator = LazyPaginator(query_func, per_page=10)

    markup = await lazy_paginated_keyboard(
        paginator=paginator,
        item_text=lambda referral_data: localize("referrals.item.format",
                                                 telegram_id=referral_data['telegram_id'],
                                                 total_earned=int(referral_data['total_earned']),
                                                 currency=EnvKeys.PAY_CURRENCY),
        item_callback=lambda referral_data: f"referral_earnings_{referral_data['telegram_id']}",
        page=page,
        back_cb="referral_system",
        nav_cb_prefix="referrals_page_"
    )

    await call.message.edit_text(
        localize("referrals.list.title"),
        reply_markup=markup
    )


async def _show_ref_earnings_page(call: CallbackQuery, referral_id: int, page: int):
    """Render one page of the caller's earnings from a specific referral."""
    user_id = call.from_user.id
    paginator = LazyPaginator(
        partial(query_referral_earnings_from_user, user_id, referral_id), per_page=10,
    )

    name = esc(await display_name(call.message.bot, referral_id))

    if page == 0 and await paginator.get_total_count() == 0:
        await call.message.edit_text(
            localize("referral.earnings.empty", id=referral_id, name=name),
            reply_markup=back("view_referrals")
        )
        return

    markup = await lazy_paginated_keyboard(
        paginator=paginator,
        item_text=lambda earning: localize("referral.earning.format",
                                           amount=int(earning.amount),
                                           currency=EnvKeys.PAY_CURRENCY,
                                           date=earning.created_at.strftime("%d.%m.%Y %H:%M"),
                                           original_amount=int(earning.original_amount)),
        item_callback=lambda earning: f"earning_detail:{earning.id}:referral_earnings_{referral_id}",
        page=page,
        back_cb="view_referrals",
        nav_cb_prefix=f"ref-earn_{referral_id}_"
    )

    title_text = localize("referral.earnings.title", telegram_id=referral_id, name=name)
    await call.message.edit_text(title_text, reply_markup=markup)


@router.callback_query(F.data.startswith("referral_earnings_"))
async def referral_earnings_handler(call: CallbackQuery, state: FSMContext):
    """Show all earnings from a specific referral with lazy loading."""
    try:
        referral_id = int(call.data.split("_")[-1])
    except (ValueError, IndexError):
        await call.answer(localize("errors.invalid_data"))
        return

    await _show_ref_earnings_page(call, referral_id, 0)


@router.callback_query(F.data.startswith("ref-earn_"))
async def referral_earnings_pagination_handler(call: CallbackQuery, state: FSMContext):
    """Pagination for a single referral's earnings. Format: ref-earn_{referral_id}_{page}"""
    try:
        _prefix, referral_id, page = call.data.split("_")
        referral_id, page = int(referral_id), int(page)
    except (ValueError, IndexError):
        await call.answer(localize("errors.pagination_invalid"))
        return

    await _show_ref_earnings_page(call, referral_id, page)


@router.callback_query(F.data == "view_all_earnings")
async def view_all_earnings_handler(call: CallbackQuery, state: FSMContext):
    """
    Show all user referral earnings with lazy loading.
    """
    user_id = call.from_user.id

    # Create paginator
    query_func = partial(query_all_referral_earnings, user_id)
    paginator = LazyPaginator(query_func, per_page=10)

    # Check if there are any earnings
    total = await paginator.get_total_count()
    if total == 0:
        await call.message.edit_text(
            localize("all.earnings.empty"),
            reply_markup=back("referral_system")
        )
        return

    markup = await lazy_paginated_keyboard(
        paginator=paginator,
        item_text=lambda earning: localize("all.earning.format",
                                           amount=int(earning.amount),
                                           currency=EnvKeys.PAY_CURRENCY,
                                           referral_id=earning.referral_id,
                                           date=earning.created_at.strftime("%d.%m.%Y %H:%M")),
        item_callback=lambda earning: f"earning_detail:{earning.id}:view_all_earnings",
        page=0,
        back_cb="referral_system",
        nav_cb_prefix="all_earnings_page_"
    )

    await call.message.edit_text(
        localize("all.earnings.title"),
        reply_markup=markup
    )


@router.callback_query(F.data.startswith("all_earnings_page_"))
async def all_earnings_pagination_handler(call: CallbackQuery, state: FSMContext):
    """
    Pagination processing for all referral earnings with lazy loading.
    """
    try:
        page = int(call.data.split("_")[-1])
    except (ValueError, IndexError):
        await call.answer(localize("errors.pagination_invalid"))
        return

    user_id = call.from_user.id

    # Create paginator
    query_func = partial(query_all_referral_earnings, user_id)
    paginator = LazyPaginator(query_func, per_page=10)

    markup = await lazy_paginated_keyboard(
        paginator=paginator,
        item_text=lambda earning: localize("all.earning.format",
                                           amount=int(earning.amount),
                                           currency=EnvKeys.PAY_CURRENCY,
                                           referral_id=earning.referral_id,
                                           date=earning.created_at.strftime("%d.%m.%Y %H:%M")),
        item_callback=lambda earning: f"earning_detail:{earning.id}:all_earnings_page_{page}",
        page=page,
        back_cb="referral_system",
        nav_cb_prefix="all_earnings_page_"
    )

    await call.message.edit_text(
        localize("all.earnings.title"),
        reply_markup=markup
    )


@router.callback_query(F.data.startswith("earning_detail:"))
async def earning_detail_handler(call: CallbackQuery, state: FSMContext):
    """
    Show details for one of the caller's own referral earnings.

    Scoped to the caller's referrer_id so one user cannot read another's
    earning rows by enumerating ids.
    """
    try:
        trash, earning_id, back_data = call.data.split(':', 2)
        earning_id = int(earning_id)
    except (ValueError, IndexError):
        await call.answer(localize("errors.invalid_data"), show_alert=True)
        return

    earning_info = await get_one_referral_earning(earning_id, referrer_id=call.from_user.id)
    if not earning_info:
        await call.answer(localize("errors.invalid_data"), show_alert=True)
        return

    await call.message.edit_text(localize('referral.item.info',
                                          id=earning_id,
                                          telegram_id=earning_info['referral_id'],
                                          name=esc(await display_name(
                                              call.message.bot, earning_info['referral_id'])),
                                          amount=earning_info['amount'],
                                          currency=EnvKeys.PAY_CURRENCY,
                                          date=earning_info['created_at'].strftime("%d.%m.%Y %H:%M"),
                                          original_amount=earning_info['original_amount']
                                          ), reply_markup=back(back_data))
    await state.clear()
