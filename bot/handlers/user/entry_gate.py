"""Entry gate: force-join channels + math captcha.

Order on every /start and menu return:
1. force-join check (skipped when the user is already in every channel)
2. captcha (only for new users; existing users are grandfathered)
3. main menu

The referral is counted only after the invitee passes the captcha — verified
signups instead of drive-by joins.
"""
import random
import time

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.filters.state import StatesGroup, State

from bot.database.methods import (
    get_force_channels, check_user_cached, check_role_cached,
)
from bot.database.methods.read import mark_captcha_passed
from bot.handlers.other import check_sub_channel
from bot.keyboards import main_menu
from bot.misc import EnvKeys
from bot.i18n import localize, esc
from bot.ui import banner, quote, cbtn, SUCCESS, PRIMARY
from bot.logger_mesh import logger

router = Router()


class GateStates(StatesGroup):
    waiting_captcha = State()


# In-memory captcha answers, keyed by user id. Small, volatile, per-process —
# exactly the lifetime a one-shot puzzle needs.
_pending_captcha: dict[int, tuple[int, int]] = {}


def _menu_text(bot_name: str, first_name: str) -> str:
    return (
        f"{banner(bot_name, localize('menu.hello', name=esc(first_name or '')))}\n\n"
        f"{localize('menu.start', name=bot_name)}"
    )


async def _open_menu(event, state: FSMContext) -> None:
    """Show the main menu for the user behind `event` (Message or CallbackQuery)."""
    user_id = event.from_user.id
    role = await check_role_cached(user_id) or 0
    bot_name = await _bot_name(event.bot)
    text = _menu_text(bot_name, event.from_user.first_name or "")
    markup = main_menu(role=role, channel=None, helper=EnvKeys.HELPER_ID)
    if isinstance(event, Message):
        await event.answer(text, reply_markup=markup)
    else:
        await event.message.edit_text(text, reply_markup=markup)
    await state.clear()


async def _bot_name(bot) -> str:
    try:
        me = await bot.me()
    except Exception:  # noqa: BLE001
        return "shop"
    name = getattr(me, "first_name", None)
    return name if isinstance(name, str) and name.strip() else "shop"


def _join_markup(channels: list[dict]) -> InlineKeyboardBuilder:
    kb = InlineKeyboardBuilder()
    for ch in channels:
        url = f"https://t.me/{ch['username']}" if ch.get("username") else None
        label = ch.get("title") or ch.get("username") or ch["chat_id"]
        if url:
            kb.row(cbtn(label, url=url, color=SUCCESS, icon="share"))
        else:
            # Private channel without a link — admin must store the username
            # or the user cannot open it; show it disabled.
            kb.row(cbtn(label, callback_data="gate_locked", color=PRIMARY, icon="lock"))
    kb.row(cbtn(localize("gate.check_joined"), "gate_check", color=SUCCESS, icon="buy"))
    return kb


async def _missing_channels(bot, user_id: int) -> list[dict]:
    """Active gate channels the user has not joined (uncheckable ones don't block)."""
    missing = []
    for ch in await get_force_channels(active_only=True):
        chat_id: str = ch["chat_id"]
        target = int(chat_id) if chat_id.lstrip("-").isdigit() else f"@{ch['username']}" if ch.get("username") else None
        if target is None:
            continue
        try:
            member = await bot.get_chat_member(chat_id=target, user_id=user_id)
        except Exception as e:  # noqa: BLE001 — bot not admin there / bad id
            logger.warning(f"force-join check skipped for {chat_id}: {e}")
            continue
        if not await check_sub_channel(member):
            missing.append(ch)
    return missing


async def run_gate(event, state: FSMContext, *, captcha: bool = True) -> bool:
    """Run the gate for this user.

    Returns True when the caller may continue showing the menu (or the gate
    just showed it itself); False when a gate screen was sent and the caller
    must stop.

    `captcha=False` skips the puzzle for in-session returns (Back to menu);
    every fresh /start verifies.
    """
    user_id = event.from_user.id
    bot = event.bot

    # 1) force-join
    missing = await _missing_channels(bot, user_id)
    if missing:
        kb = _join_markup(missing)
        text = f"{banner(localize('gate.title'))}\n\n{quote(localize('gate.join_hint'))}"
        if isinstance(event, Message):
            await event.answer(text, reply_markup=kb.as_markup())
        else:
            await event.message.edit_text(text, reply_markup=kb.as_markup())
        return False

    # 2) captcha — every /start, no exceptions
    if captcha:
        a, b = random.randint(2, 9), random.randint(2, 9)
        _pending_captcha[user_id] = (a, b, time.monotonic())
        correct = a + b
        options = {correct}
        while len(options) < 4:
            options.add(correct + random.randint(-4, 6) or correct + 1)
        opts = list(options)
        random.shuffle(opts)

        kb = InlineKeyboardBuilder()
        for val in opts:
            kb.button(text=str(val), callback_data=f"gate_cap:{val}")
        kb.adjust(2)
        kb.row(cbtn(localize("gate.captcha_another"), "gate_new_captcha", color=PRIMARY, icon="back"))

        text = (
            f"{banner(localize('gate.title'))}\n\n"
            f"{localize('gate.captcha_prompt', a=a, b=b)}\n\n"
            f"{quote(localize('gate.captcha_hint'))}"
        )
        if isinstance(event, Message):
            await event.answer(text, reply_markup=kb.as_markup())
        else:
            await event.message.edit_text(text, reply_markup=kb.as_markup())
        return False

    # 3) gate open
    return True


@router.callback_query(F.data == "gate_check")
async def gate_recheck(call: CallbackQuery, state: FSMContext):
    """User says they joined — re-run the force-join half of the gate."""
    missing = await _missing_channels(call.bot, call.from_user.id)
    if missing:
        await call.answer(localize("gate.still_not_joined"), show_alert=True)
        await call.message.edit_reply_markup(reply_markup=_join_markup(missing).as_markup())
        return
    # joined everything — captcha next (or menu)
    await call.answer(localize("gate.joined_ok"))
    ok = await run_gate(call, state)
    if ok:
        await _open_menu(call, state)


@router.callback_query(F.data == "gate_new_captcha")
async def gate_new_captcha(call: CallbackQuery, state: FSMContext):
    ok = await run_gate(call, state)
    if ok:
        await _open_menu(call, state)


@router.callback_query(F.data.startswith("gate_cap:"))
async def gate_captcha_answer(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    entry = _pending_captcha.get(user_id)
    if not entry:
        await call.answer(localize("gate.captcha_expired"), show_alert=True)
        ok = await run_gate(call, state)
        if ok:
            await _open_menu(call, state)
        return

    a, b, issued = entry
    try:
        answer = int(call.data.split(":", 1)[1])
    except ValueError:
        answer = None

    # Expire stale puzzles after 10 minutes.
    if time.monotonic() - issued > 600:
        _pending_captcha.pop(user_id, None)
        await call.answer(localize("gate.captcha_expired"), show_alert=True)
        ok = await run_gate(call, state)
        if ok:
            await _open_menu(call, state)
        return

    if answer != a + b:
        await call.answer(localize("gate.captcha_wrong"), show_alert=True)
        return

    _pending_captcha.pop(user_id, None)
    await call.answer(localize("gate.captcha_ok"))

    # Persist the pass, then count the referral (verified signup) and pay
    # the referrer's fixed reward with a notification.
    await mark_captcha_passed(user_id)
    await _credit_referral(call.bot, user_id)

    ok = True  # captcha solved; force-join already passed earlier in the flow
    missing = await _missing_channels(call.bot, user_id)
    if missing:
        ok = False
        await call.message.edit_text(
            f"{banner(localize('gate.title'))}\n\n{quote(localize('gate.join_hint'))}",
            reply_markup=_join_markup(missing).as_markup(),
        )
    if ok:
        await _open_menu(call, state)


async def _credit_referral(bot, user_id: int) -> None:
    """Credit the referrer's fixed reward for this (now verified) signup
    and notify the referrer about the money."""
    from bot.database.methods.transactions import credit_referral_reward
    from bot.database.methods.read import check_user
    try:
        credited = await credit_referral_reward(user_id)
    except Exception as e:  # noqa: BLE001 — reward must never block entry
        logger.warning(f"referral reward credit failed for {user_id}: {e}")
        return
    if not credited:
        return

    row = await check_user(user_id)
    referrer = row.get("referral_id") if row else None
    if not referrer:
        return
    invitee = esc(call_first_name(user_id, row))
    try:
        await bot.send_message(
            referrer,
            localize("referral.credited_notify",
                     amount=EnvKeys.REFERRAL_REWARD, name=invitee),
        )
    except Exception as e:  # noqa: BLE001 — referrer may have blocked the bot
        logger.debug(f"referral notify to {referrer} failed: {e}")


def call_first_name(user_id: int, row: dict) -> str:
    """Best-effort invitee name for the reward message."""
    return str(row.get("first_name") or user_id)


@router.callback_query(F.data == "gate_locked")
async def gate_locked(call: CallbackQuery):
    await call.answer(localize("gate.locked"), show_alert=True)
