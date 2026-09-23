"""INR UPI top-up: dynamic amount-locked QR -> UTR -> screenshot -> verification.

Flow
1. user picks UPI and enters an amount
2. bot renders a clean UPI QR for that exact amount (no logo, no styling)
3. user pays, submits the UTR reference
4. user sends the payment screenshot
5. bot forwards it to the payment log room with username/id/amount/UTR and
   Verify / Deny buttons wired to owner + sudo only
6. on verify the balance is credited; on deny the request is closed
"""
from decimal import Decimal

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, BufferedInputFile
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

import qrcode
import io

from bot.database.methods import (
    upi_create_request, upi_set_utr, upi_set_verifying, upi_get_request,
    upi_approve, upi_deny, process_payment_with_referral, create_pending_payment,
)
from bot.database.methods.audit import log_audit
from bot.database.methods.cache_utils import safe_create_task
from bot.database.methods.read import invalidate_user_cache
from bot.handlers.other import caller_name
from bot.keyboards import back, close
from bot.logger_mesh import logger
from bot.misc import EnvKeys
from bot.i18n import localize, esc
from bot.states import BalanceStates
from bot.ui import banner, quote, kv, cbtn, SUCCESS, DANGER

router = Router()

# callback_data layout keeps ids short: upi_go | upi_utr | upi_ss:<req> |
# upi_ok:<req> | upi_no:<req>
_UTR_RE = r"^[0-9A-Za-z]{8,22}$"


def _upi_uri(amount: Decimal) -> str:
    """Standard UPI deep link for any UPI app (GPay/PhonePe/Paytm/BHIM)."""
    name = EnvKeys.UPI_NAME or "Shop"
    upi = EnvKeys.UPI_ID
    note = f"topup {amount}"
    return (
        f"upi://pay?pa={upi}&pn={name}"
        f"&am={amount.quantize(Decimal('0.01'))}&cu=INR&tn={note}"
    )


def _qr_png(payload: str) -> bytes:
    """Clean black/white QR — no logo, no rounded modules, max contrast."""
    img = qrcode.make(payload, box_size=10, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _is_reviewer(user_id: int) -> bool:
    """Only OWNER and SUDO ids may approve/deny payments."""
    return EnvKeys.is_sudo(user_id)


@router.callback_query(F.data == "pay_upi")
async def upi_start(call: CallbackQuery, state: FSMContext):
    """Entry point from the payment-choice keyboard."""
    if not EnvKeys.UPI_ID:
        await call.answer(localize("payments.not_configured"), show_alert=True)
        return
    data = await state.get_data()
    amount = data.get("amount")
    if not amount:
        await call.answer(localize("payments.session_expired"), show_alert=True)
        return

    req_id = await upi_create_request(call.from_user.id, Decimal(amount))
    await state.update_data(upi_req=req_id)

    png = _qr_png(_upi_uri(Decimal(amount)))
    caption = "\n".join([
        banner(localize("upi.title")),
        kv(localize("upi.amount_key"), f"₹{amount}"),
        kv(localize("upi.upi_key"), f"<code>{esc(EnvKeys.UPI_ID)}</code>"),
        "",
        quote(localize("upi.scan_hint")),
    ])

    # QR ke niche: green Send UTR + blue Back.
    kb = _utr_kb()
    try:
        sent = await call.message.answer_photo(
            BufferedInputFile(png, filename=f"upi-{amount}.png"),
            caption=caption,
            reply_markup=kb,
        )
        try:
            await call.message.delete()
        except (TelegramBadRequest, TelegramForbiddenError):
            pass
        del sent  # photo stays; buttons are already attached
    except Exception as e:  # noqa: BLE001 — photo send can fail on odd clients
        logger.warning(f"QR send failed: {e}")
        await call.message.edit_text(caption, reply_markup=kb)


def _utr_kb():
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    kb.row(cbtn(localize("upi.btn.send_utr"), "upi_ask_utr", color=SUCCESS, icon="key"))
    kb.row(cbtn(localize("btn.back"), "replenish_balance", color=PRIMARY, icon="back"))
    return kb.as_markup()


def _screenshot_kb():
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    kb.row(cbtn(localize("upi.btn.send_screenshot"), "upi_ask_ss", color=SUCCESS, icon="share"))
    kb.row(cbtn(localize("btn.back"), "replenish_balance", color=PRIMARY, icon="back"))
    return kb.as_markup()


@router.callback_query(F.data == "upi_ask_utr")
async def upi_ask_utr(call: CallbackQuery, state: FSMContext):
    """Prompt for the UTR (green button on the QR card)."""
    await call.message.answer(localize("upi.utr_prompt"), reply_markup=back("replenish_balance"))
    await state.set_state(BalanceStates.waiting_utr)
    await call.answer()


@router.message(BalanceStates.waiting_utr)
async def upi_utr(message: Message, state: FSMContext):
    """Accept the 12-digit UTR, then offer the screenshot button."""
    utr = (message.text or "").strip()
    if not utr:
        return
    data = await state.get_data()
    req_id = data.get("upi_req")

    if not req_id:
        await state.clear()
        await message.answer(localize("payments.session_expired"), reply_markup=back("profile"))
        return

    import re as _re
    if not _re.match(_UTR_RE, utr):
        await message.answer(localize("upi.utr_invalid"))
        return

    await upi_set_utr(req_id, utr)
    await state.update_data(upi_utr=utr)
    await message.answer(
        localize("upi.screenshot_prompt"),
        reply_markup=_screenshot_kb(),
    )
    await state.clear()


@router.callback_query(F.data == "upi_ask_ss")
async def upi_ask_ss(call: CallbackQuery, state: FSMContext):
    """Prompt for the payment screenshot (green button after the UTR)."""
    data = await state.get_data()
    if not data.get("upi_req") or not data.get("upi_utr"):
        await call.answer(localize("payments.session_expired"), show_alert=True)
        return
    await message_state_ask_ss(call, state)


async def message_state_ask_ss(call: CallbackQuery, state: FSMContext):
    await call.message.answer(localize("upi.screenshot_prompt"), reply_markup=back("replenish_balance"))
    await state.set_state(BalanceStates.waiting_screenshot)
    await call.answer()


@router.message(BalanceStates.waiting_screenshot, F.photo)
async def upi_screenshot(message: Message, state: FSMContext):
    """Forward the screenshot to the review room with Verify/Deny buttons."""
    data = await state.get_data()
    req_id = data.get("upi_req")
    amount = data.get("amount")
    utr = data.get("upi_utr") or ""
    if not req_id:
        await state.clear()
        await message.answer(localize("payments.session_expired"), reply_markup=back("profile"))
        return

    room = EnvKeys.PAYMENT_LOG_GROUP_ID or EnvKeys.LOG_GROUP_ID
    if not room:
        # No review room configured — log it and ask the user to wait.
        await upi_set_verifying(req_id)
        await log_audit("upi_no_room", level="WARNING", user_id=message.from_user.id,
                        resource_type="Payment", details=f"req={req_id} amount={amount}")
        await message.answer(localize("upi.sent_no_room"), reply_markup=close())
        await state.clear()
        return

    user = message.from_user
    caption = "\n".join([
        f"<b>{localize('upi.review.title')}</b>",
        kv(localize("upi.review.user"), f"{esc(caller_name(message))} · <code>{user.id}</code>"),
        kv(localize("upi.review.username"), f"@{user.username or '—'}"),
        kv(localize("upi.review.amount"), f"₹{amount}"),
        kv(localize("upi.review.utr"), f"<code>{esc(utr)}</code>"),
        kv(localize("upi.review.req"), f"#{req_id}"),
    ])

    kb = _review_kb(req_id) if _is_reviewer_safe() else None
    try:
        sent = await message.bot.send_photo(
            chat_id=room,
            photo=message.photo[-1].file_id,
            caption=caption,
            reply_markup=kb,
        )
        await upi_set_verifying(req_id, sent.message_id)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"review room send failed: {e}")
        await upi_set_verifying(req_id)

    await log_audit("upi_submitted", user_id=user.id, resource_type="Payment",
                    details=f"req={req_id}, amount={amount}, utr={utr}")
    await message.answer(localize("upi.submitted"), reply_markup=close())
    await state.clear()


def _is_reviewer_safe() -> bool:
    """The bot itself can always post buttons; access is re-checked on click."""
    return True


def _review_kb(req_id: int):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    kb.row(
        cbtn(localize("upi.review.verify"), f"upi_ok:{req_id}", color=SUCCESS, icon="buy"),
        cbtn(localize("upi.review.deny"), f"upi_no:{req_id}", color=DANGER, icon="minus"),
    )
    return kb.as_markup()


async def _require_reviewer(call: CallbackQuery) -> bool:
    if _is_reviewer(call.from_user.id):
        return True
    await call.answer(localize("upi.review.only_admins"), show_alert=True)
    return False


@router.callback_query(F.data.startswith("upi_ok:"))
async def upi_verify(call: CallbackQuery, state: FSMContext):
    if not await _require_reviewer(call):
        return
    try:
        req_id = int(call.data.split(":", 1)[1])
    except ValueError:
        return

    req = await upi_approve(req_id)
    if not req:
        await call.answer(localize("upi.review.already_done"), show_alert=True)
        return

    # Credit through the standard idempotent path so Payments keeps a record.
    success, code = await process_payment_with_referral(
        user_id=req["user_id"],
        amount=Decimal(str(req["amount"])),
        provider="upi",
        external_id=f"upi-{req_id}",
        referral_percent=EnvKeys.REFERRAL_PERCENT,
    )
    if not success:
        logger.warning(f"upi credit failed req={req_id}: {code}")

    await log_audit("upi_approved", user_id=call.from_user.id,
                    resource_type="Payment", resource_id=str(req_id),
                    details=f"amount={req['amount']}, buyer={req['user_id']}, credit={success}")
    safe_create_task(invalidate_user_cache(req["user_id"]))

    await call.answer(localize("upi.review.approved"))
    try:
        await call.message.edit_reply_markup(reply_markup=None)
        await call.message.answer(localize(
            "upi.review.done", req=req_id, amount=req["amount"]),)
    except (TelegramBadRequest, TelegramForbiddenError):
        pass

    try:
        await call.bot.send_message(
            req["user_id"],
            localize("upi.credited", amount=req["amount"], currency=EnvKeys.PAY_CURRENCY),
            reply_markup=close(),
        )
    except (TelegramBadRequest, TelegramForbiddenError) as e:
        logger.warning(f"credit notice failed: {e}")


@router.callback_query(F.data.startswith("upi_no:"))
async def upi_deny_cb(call: CallbackQuery, state: FSMContext):
    if not await _require_reviewer(call):
        return
    try:
        req_id = int(call.data.split(":", 1)[1])
    except ValueError:
        return
    req = await upi_get_request(req_id)
    await upi_deny(req_id)
    await log_audit("upi_denied", user_id=call.from_user.id,
                    resource_type="Payment", resource_id=str(req_id),
                    details=f"buyer={req.get('user_id') if req else '?'}")
    await call.answer(localize("upi.review.denied"))
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except (TelegramBadRequest, TelegramForbiddenError):
        pass
    if req:
        try:
            await call.bot.send_message(req["user_id"], localize("upi.rejected", req=req_id))
        except (TelegramBadRequest, TelegramForbiddenError):
            pass
