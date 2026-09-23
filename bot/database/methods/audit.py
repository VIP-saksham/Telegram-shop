# =============================================================================
#  Copyright (c) 2026 Saksham Swaroop (@truenakshu)  |  GitHub: VIP-saksham
#  LinkedIn: sakshamswaroop
#
#  All rights reserved. This source code is the private property of the
#  author. Copying, modifying, redistributing or deploying any part of this
#  file WITHOUT the author's written permission is strictly prohibited.
#  For licensing / permission: https://t.me/truenakshu
# =============================================================================

import asyncio
import logging
import os
from datetime import datetime, timezone

from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.main import Database
from bot.database.models.main import AuditLog
from bot.logger_mesh import audit_logger

_LOG_LEVELS = {
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
}


def _is_money_action(action: str) -> bool:
    """Whether this audit action belongs in the money room (payments+purchases)."""
    a = (action or "").lower()
    return any(k in a for k in ("payment", "crypto", "stars", "fiat", "topup",
                                "replenish", "invoice", "referral_bonus",
                                "purchase", "cart", "buy", "checkout"))


def _log_group_enabled() -> bool:
    """Whether any Telegram log group is configured and not explicitly disabled."""
    if os.getenv("LOG_GROUP_EVENTS", "all").lower() == "off":
        return False
    return bool(os.getenv("LOG_GROUP_ID", "").strip() or os.getenv("PAYMENT_LOG_GROUP_ID", "").strip())


def _log_group_wants(action: str, level: str) -> bool:
    """Filter which audit actions are mirrored to the log group.

    LOG_GROUP_EVENTS holds a comma-separated list of event classes:
    all, payments, purchases, admin, security, errors
    """
    raw = os.getenv("LOG_GROUP_EVENTS", "all").lower()
    classes = {c.strip() for c in raw.split(",") if c.strip()}
    if "all" in classes or not classes:
        return True
    a = (action or "").lower()
    l = (level or "").upper()
    checks = {
        "payments": ("payment", "crypto", "stars", "fiat", "topup", "replenish", "invoice", "referral"),
        "purchases": ("purchase", "cart", "buy", "checkout", "restock", "item_", "stock"),
        "admin": ("admin", "role", "promo", "sale", "catalog", "category", "position",
                  "broadcast", "maintenance", "user", "assign", "balance_change", "delete"),
        "security": ("ban", "block", "rate", "security", "replay", "unblock", "auth"),
        "errors": lambda: l in ("WARNING", "ERROR"),
    }
    for c in classes:
        check = checks.get(c)
        if check is None:
            continue
        if callable(check):
            if check():
                return True
        elif any(k in a for k in check):
            return True
    return False


def _format_audit_line(action: str, level: str, user_id, resource_type, resource_id, details, ip_address) -> str:
    """Render an audit entry as a styled HTML card for the log group."""
    from html import escape as _esc

    badges = {
        "INFO": "🔹",
        "WARNING": "⚠️",
        "ERROR": "🚨",
    }
    # Friendly premium-emoji labels for the common actions.
    pretty = {
        "user_start": ("👤", "New session"),
        "bot_online": ("🟢", "Bot online"),
        "balance_replenish": ("💰", "Balance top-up"),
        "referral_signup_reward": ("🎁", "Referral reward"),
        "promo_redeem": ("🎫", "Coupon redeemed"),
        "purchase": ("🛒", "Purchase"),
        "cart_checkout": ("🛍", "Checkout"),
        "broadcast_sent": ("📢", "Broadcast"),
        "upi_submitted": ("🧾", "UPI proof submitted"),
        "upi_verified": ("✅", "UPI verified"),
        "upi_denied": ("❌", "UPI denied"),
    }
    glyph, pretty_action = pretty.get((action or "").lower()), None
    if glyph:
        glyph, pretty_action = glyph
    badge = badges.get(level.upper(), "🔹")
    head = _esc(pretty_action or str(action))
    line = f"{badge} <b>{head}</b>"
    parts = []
    if user_id is not None:
        parts.append(f"👤 <a href='tg://user?id={user_id}'>{user_id}</a>")
    if resource_type:
        parts.append(f"📦 {_esc(str(resource_type))}")
    if resource_id:
        parts.append(f"🆔 <code>{_esc(str(resource_id))}</code>")
    if details:
        d = _esc(str(details))
        if len(d) > 400:
            d = d[:400] + "…"
        parts.append(f"📝 {d}")
    if ip_address:
        parts.append(f"🌐 <code>{_esc(str(ip_address))}</code>")
    if parts:
        line += "\n" + "\n".join(parts)
    stamp = datetime.now(timezone.utc).strftime("%d.%m %H:%M:%S UTC")
    return f"{line}\n🕘 {stamp}"


async def _send_to_log_group(chat_id: str, text: str) -> None:
    """Fire-and-forget delivery of one HTML message to one log group."""
    from aiogram import Bot
    from aiogram.client.default import DefaultBotProperties
    from aiogram.exceptions import TelegramAPIError

    if not chat_id:
        return
    try:
        bot = Bot(
            token=os.getenv("TOKEN", ""),
            default=DefaultBotProperties(parse_mode="HTML"),
        )
        async with bot:
            await bot.send_message(chat_id, text, disable_web_page_preview=True)
    except TelegramAPIError as e:
        audit_logger.warning("Log group send failed: %s", e)
    except Exception as e:
        audit_logger.debug("Log group send error: %s", e)


def notify_log_group(action: str, level: str, user_id, resource_type, resource_id, details, ip_address) -> None:
    """Queue a mirror of this audit entry to the Telegram log group(s).

    Money events (payments + purchases) go to PAYMENT_LOG_GROUP_ID when set;
    everything else goes to LOG_GROUP_ID. Never blocks or raises: logging
    must not be able to take the bot down.
    """
    if not _log_group_enabled():
        return
    if not _log_group_wants(action, level):
        return
    text = _format_audit_line(action, level, user_id, resource_type, resource_id, details, ip_address)
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    # Money trail gets its own room so it never drowns between admin chatter.
    money = _is_money_action(action)
    chat_id = (os.getenv("PAYMENT_LOG_GROUP_ID", "").strip() if money
               else os.getenv("LOG_GROUP_ID", "").strip())
    if not chat_id:
        chat_id = os.getenv("LOG_GROUP_ID", "").strip()
    if not chat_id:
        return
    task = loop.create_task(_send_to_log_group(chat_id, text))
    _log_group_tasks.add(task)
    task.add_done_callback(_log_group_tasks.discard)


# Bounded set of in-flight mirror tasks (keeps a reference so tasks aren't GC'd mid-send).
_log_group_tasks: set = set()


class AuditBuffer:
    """Collects audit rows and writes them out in batches.

    Buffering is only active while a flusher task is running: outside the bot
    process (tests, scripts) log_audit writes through immediately, so a caller
    that awaits it can still read the row back straight after.

    The file log is always written synchronously by log_audit, so a crash loses
    at most the DB copy of the last few seconds — never the audit trail itself.
    """

    MAX_BATCH = 50          # flush as soon as this many rows are waiting
    FLUSH_INTERVAL = 2.0    # ...or this long after the first one arrived
    MAX_BUFFERED = 10_000   # hard cap; beyond this rows are written through

    def __init__(self):
        self._rows: list[dict] = []
        self._wakeup = asyncio.Event()
        self._task: asyncio.Task | None = None

    @property
    def active(self) -> bool:
        return self._task is not None and not self._task.done()

    def add(self, row: dict) -> bool:
        """Queue a row. False if the caller should write it through itself."""
        if not self.active or len(self._rows) >= self.MAX_BUFFERED:
            return False
        self._rows.append(row)
        if len(self._rows) >= self.MAX_BATCH:
            self._wakeup.set()
        return True

    async def flush(self) -> int:
        """Write everything buffered so far. Returns the number of rows written."""
        if not self._rows:
            return 0
        batch, self._rows = self._rows, []
        try:
            async with Database().session() as s:
                await s.execute(insert(AuditLog), batch)
            return len(batch)
        except Exception:
            # The rows are already in the file log, so this is a degraded DB
            # copy rather than lost history. Dropping them keeps a persistent
            # DB failure from growing the buffer without bound.
            audit_logger.warning(
                "Failed to write %d buffered audit entries to DB", len(batch),
                exc_info=True,
            )
            return 0

    async def _run(self) -> None:
        while True:
            try:
                await asyncio.wait_for(self._wakeup.wait(), timeout=self.FLUSH_INTERVAL)
            except asyncio.TimeoutError:
                pass
            except asyncio.CancelledError:
                raise
            self._wakeup.clear()
            await self.flush()

    async def start(self) -> None:
        if self.active:
            return
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        """Stop the flusher and write out whatever is still buffered."""
        task, self._task = self._task, None
        if task is not None:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
        await self.flush()


_audit_buffer = AuditBuffer()


def get_audit_buffer() -> AuditBuffer:
    """The process-wide audit buffer (started at boot, drained on shutdown)."""
    return _audit_buffer


async def start_audit_buffer() -> None:
    await _audit_buffer.start()


async def stop_audit_buffer() -> None:
    await _audit_buffer.stop()


async def log_audit(
    action: str,
    *,
    level: str = "INFO",
    user_id: int | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    details: str | None = None,
    ip_address: str | None = None,
    session: AsyncSession | None = None,
) -> None:
    """Write audit entry to the log file, the database and the Telegram log group.

    When 'session' is given, the DB row is added to that session so it
    commits (or rolls back) atomically with the caller's transaction. It avoids a phantom audit
    row surviving a rolled-back parent and avoids taking a second pooled
    connection while row locks are held. Such a row is never buffered — it has
    to share the caller's transaction.

    Without a session the row goes through the batching buffer when one is
    running, and straight to its own short-lived session otherwise.
    """
    # 1. File log
    log_level = _LOG_LEVELS.get(level, logging.INFO)
    parts = [f"action={action}"]
    if user_id is not None:
        parts.append(f"user={user_id}")
    if resource_type:
        parts.append(f"resource={resource_type}")
    if resource_id:
        parts.append(f"id={resource_id}")
    if details:
        parts.append(details)
    if ip_address:
        parts.append(f"ip={ip_address}")
    audit_logger.log(log_level, " | ".join(parts))

    # 2. Telegram log group (fire-and-forget, must never break the caller)
    try:
        notify_log_group(action, level, user_id, resource_type, resource_id, details, ip_address)
    except Exception:
        audit_logger.debug("notify_log_group failed", exc_info=True)

    # 3. Database log
    try:
        if session is not None:
            # Enlist in the caller's transaction; the caller's commit/rollback decides this row's fate.
            session.add(AuditLog(
                level=level,
                user_id=user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                details=details,
                ip_address=ip_address,
            ))
            return

        # Stamped now, not at flush time, so a batched row keeps the moment it describes rather than the moment it was written.
        row = {
            "timestamp": datetime.now(timezone.utc),
            "level": level,
            "user_id": user_id,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "details": details,
            "ip_address": ip_address,
        }
        if _audit_buffer.add(row):
            return

        async with Database().session() as s:
            await s.execute(insert(AuditLog), [row])
    except Exception:
        audit_logger.warning("Failed to write audit entry to DB", exc_info=True)


def log_audit_bg(action: str, **kwargs) -> None:
    """Schedule log_audit without blocking the caller.

    For request-path call sites where the reply must not wait for the audit
    INSERT. Not usable with session= — an enlisted row must stay inside the
    caller's transaction, so those calls remain awaited.
    """
    from bot.database.methods.cache_utils import safe_create_task
    safe_create_task(log_audit(action, **kwargs))
