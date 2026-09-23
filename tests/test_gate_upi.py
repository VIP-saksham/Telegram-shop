"""Tests for the entry gate, UPI flow, force channels and referral reward."""
import base64
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.database.methods.read import (
    CAPTCHA_SINCE, get_captcha_passed, get_force_channels,
)
from bot.database.methods.create import add_force_channel, upi_create_request, upi_approve
from bot.handlers.admin.force_channels import _parse_link
from bot.handlers.user.upi_payment import _upi_uri, _qr_png, _is_reviewer
from bot.handlers.user.entry_gate import _pending_captcha
from bot.misc import EnvKeys


# --- Force-channel link parsing --------------------------------------------

class TestParseLink:
    def test_tme_link(self):
        assert _parse_link("https://t.me/mychannel") == ("@mychannel", "mychannel")

    def test_at_link(self):
        assert _parse_link("@mychannel") == ("@mychannel", "mychannel")

    def test_numeric_id(self):
        assert _parse_link("-1001234567890") == ("-1001234567890", None)

    def test_garbage(self):
        assert _parse_link("hello world") is None
        assert _parse_link("") is None


# --- UPI QR ------------------------------------------------------------------

class TestUpiQr:
    def test_uri_contains_amount_and_payee(self):
        uri = _upi_uri(Decimal("150"))
        assert uri.startswith("upi://pay?")
        assert "am=150.00" in uri
        assert "cu=INR" in uri

    def test_qr_png_is_real_png(self):
        png = _qr_png(_upi_uri(Decimal("100")))
        assert png[:8] == b"\x89PNG\r\n\x1a\n"

    def test_reviewer_gate(self):
        with patch.object(EnvKeys, "OWNER_ID", 111), patch.object(EnvKeys, "SUDO_ID_LIST", (222,)):
            assert _is_reviewer(111) is True
            assert _is_reviewer(222) is True
            assert _is_reviewer(999) is False


# --- UPI request lifecycle ---------------------------------------------------

class TestUpiRequestLifecycle:
    async def test_create_approve(self, setup_test_database):
        req_id = await upi_create_request(500100, Decimal("250"))
        assert req_id

        req = await upi_approve(req_id)
        assert req is not None
        assert req["amount"] == Decimal("250.00")

        # Second approve is refused — already processed.
        assert await upi_approve(req_id) is None


# --- Force channels storage ---------------------------------------------------

class TestForceChannelsStore:
    async def test_add_and_list(self, setup_test_database):
        created = await add_force_channel("@gate_chan", username="gate_chan", title="Gate")
        assert created is True
        # duplicate is refused
        assert await add_force_channel("@gate_chan", username="gate_chan") is False

        chans = await get_force_channels(active_only=True)
        assert any(ch["username"] == "gate_chan" for ch in chans)


# --- Captcha flag -------------------------------------------------------------

async def _set_reg_date(telegram_id: int, ts: float) -> None:
    from sqlalchemy import update as sa_update
    from bot.database.main import Database
    from bot.database.models.main import User
    async with Database().session() as s:
        await s.execute(
            sa_update(User).where(User.telegram_id == telegram_id).values(
                registration_date=datetime.fromtimestamp(ts, tz=timezone.utc),
            )
        )


class TestCaptchaFlag:
    async def test_grandfathered_user(self, setup_test_database, user_factory):
        # Old user (pre-captcha) counts as passed even with flag NULL.
        await user_factory(telegram_id=770001)
        await _set_reg_date(770001, CAPTCHA_SINCE - 10)
        assert await get_captcha_passed(770001) is True

    async def test_new_unverified_user(self, setup_test_database, user_factory):
        await user_factory(telegram_id=770002)
        await _set_reg_date(770002, CAPTCHA_SINCE + 10)
        assert await get_captcha_passed(770002) is False
