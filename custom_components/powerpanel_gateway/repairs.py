"""Repair flows for PowerPanel Gateway issues."""

from __future__ import annotations

from typing import Any

from homeassistant.components.repairs import ConfirmRepairFlow, RepairsFlow
from homeassistant.core import HomeAssistant


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, Any] | None,
) -> RepairsFlow:
    """Return a repair flow for a raised issue.

    Both current issues (``cannot_connect``, ``auth_failed``) are resolved by the
    user fixing connectivity/credentials; a simple confirm flow lets them dismiss
    the issue once addressed (the coordinator clears it on the next good poll).
    """
    return ConfirmRepairFlow()
