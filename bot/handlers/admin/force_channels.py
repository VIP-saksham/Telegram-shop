"""Admin management of the force-join channel gate."""
import re

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.filters.state import StatesGroup, State

from bot.database.methods import add_force_channel, remove_force_channel, set_force_channel_active
from bot.database.methods.read import get_force_channels
from bot.filters import HasPermissionFilter
from bot.database.models import Permission
from bot.keyboards import back, force_channels_admin_kb
from bot.misc import EnvKeys
from bot.i18n import localize, esc
from bot.ui import banner
from bot.logger_mesh import logger

router = Router()


class ForceChannelStates(StatesGroup):
    waiting_link = State()


_TME_RE = re.compile(r"(?:https?://)?t\.me/(@?[A-Za-z0-9_]{4,64})/?$")
_AT_RE = re.compile(r"^@([A-Za-z0-9_]{4,64})$")
_ID_RE = re.compile(r"^-100\d{6,}$|^-\d{5,}$")


def _parse_link(text: str) -> tuple[str, str | None] | None:
    """Return (chat_id, username) or None when unparseable."""
    raw = (text or "").strip()
    if not raw:
        return None
    m = _ID_RE.match(raw)
    if m:
        return raw, None
    m = _TME_RE.match(raw) or _AT_RE.match(raw)
    if m:
        username = m.group(1).lstrip("@")
        return f"@{username}", username
    return None


@router.callback_query(
    F.data == "force_channels",
    HasPermissionFilter(permission=Permission.SETTINGS_MANAGE),
)
async def force_channels_menu(call: CallbackQuery, state: FSMContext):
    channels = await get_force_channels(active_only=False)
    text = f"{banner(localize('admin.fc.menu'))}\n\n{localize('admin.fc.hint')}"
    await call.message.edit_text(text, reply_markup=force_channels_admin_kb(channels))
    await state.clear()


@router.callback_query(
    F.data == "fc_add",
    HasPermissionFilter(permission=Permission.SETTINGS_MANAGE),
)
async def fc_add_start(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text(localize("admin.fc.send_link"), reply_markup=back("force_channels"))
    await state.set_state(ForceChannelStates.waiting_link)


@router.message(ForceChannelStates.waiting_link)
async def fc_add_link(message: Message, state: FSMContext):
    parsed = _parse_link(message.text)
    if not parsed:
        await message.answer(localize("admin.fc.bad_link"))
        return
    chat_id, username = parsed

    # Resolve the title while the admin is here (best effort).
    title = None
    try:
        chat = await message.bot.get_chat(chat_id if chat_id.startswith("@") or chat_id.startswith("-") else int(chat_id))
        title = getattr(chat, "title", None) or None
        if username is None and getattr(chat, "username", None):
            username = chat.username
    except Exception as e:  # noqa: BLE001 — bot may not be added yet
        logger.debug(f"get_chat({chat_id}) failed: {e}")

    created = await add_force_channel(chat_id, username=username, title=title)
    await message.answer(
        localize("admin.fc.added") if created else localize("admin.fc.exists"),
        reply_markup=back("force_channels"),
    )
    await state.clear()


@router.callback_query(
    F.data.startswith("fc_del:"),
    HasPermissionFilter(permission=Permission.SETTINGS_MANAGE),
)
async def fc_delete(call: CallbackQuery, state: FSMContext):
    chat_id = call.data.split(":", 1)[1]
    await remove_force_channel(chat_id)
    await call.answer(localize("admin.fc.removed"))
    channels = await get_force_channels(active_only=False)
    text = f"{banner(localize('admin.fc.menu'))}\n\n{localize('admin.fc.hint')}"
    await call.message.edit_text(text, reply_markup=force_channels_admin_kb(channels))


@router.callback_query(
    F.data.startswith("fc_toggle:"),
    HasPermissionFilter(permission=Permission.SETTINGS_MANAGE),
)
async def fc_toggle(call: CallbackQuery, state: FSMContext):
    chat_id = call.data.split(":", 1)[1]
    channels = await get_force_channels(active_only=False)
    current = next((ch for ch in channels if ch["chat_id"] == chat_id), None)
    if not current:
        await call.answer(localize("errors.invalid_data"), show_alert=True)
        return
    await set_force_channel_active(chat_id, not current["is_active"])
    await call.answer(localize("admin.fc.toggled"))
    channels = await get_force_channels(active_only=False)
    text = f"{banner(localize('admin.fc.menu'))}\n\n{localize('admin.fc.hint')}"
    await call.message.edit_text(text, reply_markup=force_channels_admin_kb(channels))
