"""Diagnostics for the PowerPanel Gateway config entry."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_API_TOKEN
from .coordinator import PowerPanelCoordinator

# Redact secrets and anything host-identifying we don't need in a bug report.
TO_REDACT = {CONF_API_TOKEN, "host", "smtp_username", "smtp_to", "smtp_from"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    coordinator: PowerPanelCoordinator = entry.runtime_data
    data = coordinator.data

    gateway_diag: dict[str, Any] = {}
    try:
        gateway_diag = await coordinator.client.async_get_diagnostics()
    except Exception as err:
        gateway_diag = {"error": str(err)}

    return {
        "entry": {
            "title": entry.title,
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": async_redact_data(dict(entry.options), TO_REDACT),
        },
        "status": data.status if data else {},
        "config": async_redact_data(data.config if data else {}, TO_REDACT),
        "shutdown": data.shutdown if data else {},
        "gateway_diagnostics": async_redact_data(gateway_diag, TO_REDACT),
    }
