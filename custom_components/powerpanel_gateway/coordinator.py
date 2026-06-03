"""DataUpdateCoordinator for PowerPanel Gateway.

Polls the gateway for status + config and, on each cycle, fires Home Assistant
bus events for any *new* gateway events since the last poll.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    GatewayApiClient,
    GatewayAuthError,
    GatewayConnectionError,
)
from .const import (
    CONF_API_TOKEN,
    CONF_HOST,
    CONF_POLL_INTERVAL,
    CONF_PORT,
    CONF_SSL,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
    GATEWAY_EVENT_TO_HA_EVENT,
    ISSUE_AUTH_FAILED,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class GatewayData:
    """Snapshot returned by the coordinator each cycle."""

    status: dict[str, Any] = field(default_factory=dict)
    config: dict[str, Any] = field(default_factory=dict)
    shutdown: dict[str, Any] = field(default_factory=dict)


class PowerPanelCoordinator(DataUpdateCoordinator[GatewayData]):
    """Coordinates polling and event fan-out for one gateway."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.config_entry = entry
        options = {**entry.data, **entry.options}
        interval = int(options.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL))
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=interval),
        )
        self.client = GatewayApiClient(
            async_get_clientsession(hass),
            options[CONF_HOST],
            options[CONF_PORT],
            use_ssl=options.get(CONF_SSL, False),
            token=options.get(CONF_API_TOKEN) or None,
        )
        self._last_event_id: int | None = None
        self._primed = False

    async def _async_update_data(self) -> GatewayData:
        try:
            status = await self.client.async_get_status()
            config = await self.client.async_get_config()
            shutdown = await self.client.async_evaluate_shutdown()
            events = await self.client.async_get_events(limit=50)
        except GatewayAuthError as err:
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                ISSUE_AUTH_FAILED,
                is_fixable=True,
                severity=ir.IssueSeverity.ERROR,
                translation_key=ISSUE_AUTH_FAILED,
            )
            raise UpdateFailed(f"Authentication failed: {err}") from err
        except GatewayConnectionError as err:
            raise UpdateFailed(str(err)) from err

        ir.async_delete_issue(self.hass, DOMAIN, ISSUE_AUTH_FAILED)
        self._fire_new_events(events)
        return GatewayData(status=status, config=config, shutdown=shutdown)

    def _fire_new_events(self, events: list[dict[str, Any]]) -> None:
        """Fire HA bus events for gateway events newer than the last seen id.

        ``/api/events`` returns newest-first. On the first poll we only record the
        high-water mark so we don't replay history on startup.
        """
        if not events:
            return
        newest_id = events[0].get("id")
        if not self._primed:
            self._primed = True
            self._last_event_id = newest_id
            return

        new_events = [
            e
            for e in events
            if self._last_event_id is None or (e.get("id") or 0) > self._last_event_id
        ]
        for event in reversed(new_events):  # oldest first
            ha_event = GATEWAY_EVENT_TO_HA_EVENT.get(event.get("type", ""))
            if ha_event is None:
                continue
            self.hass.bus.async_fire(
                ha_event,
                {
                    "type": event.get("type"),
                    "message": event.get("message"),
                    "state": event.get("state"),
                    "battery_percent": event.get("battery_percent"),
                    "remaining_runtime_minutes": event.get("remaining_runtime_minutes"),
                    "timestamp": event.get("timestamp"),
                    "entry_id": self.config_entry.entry_id,
                },
            )
            _LOGGER.debug("Fired %s for gateway event %s", ha_event, event.get("type"))

        if newest_id is not None:
            self._last_event_id = newest_id
