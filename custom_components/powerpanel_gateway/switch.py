"""Switch platform for PowerPanel Gateway.

Switches reflect and toggle gateway config flags (email alerts and the shutdown
policy enable flag). They write through the REST API and refresh the coordinator.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import GatewayApiClient, GatewayError
from .coordinator import PowerPanelCoordinator
from .entity import PowerPanelEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class PowerPanelSwitchDescription(SwitchEntityDescription):
    """Switch description with config read + write hooks."""

    is_on_fn: Callable[[dict[str, Any]], bool]
    set_fn: Callable[[GatewayApiClient, bool], Awaitable[Any]]


SWITCHES: tuple[PowerPanelSwitchDescription, ...] = (
    PowerPanelSwitchDescription(
        key="ups_email_alerts",
        translation_key="ups_email_alerts",
        icon="mdi:email-alert",
        device_class=SwitchDeviceClass.SWITCH,
        is_on_fn=lambda cfg: bool(cfg.get("email", {}).get("enabled")),
        set_fn=lambda c, on: c.async_set_email_enabled(on),
    ),
    PowerPanelSwitchDescription(
        key="ups_shutdown_policy",
        translation_key="ups_shutdown_policy",
        icon="mdi:power-settings",
        device_class=SwitchDeviceClass.SWITCH,
        is_on_fn=lambda cfg: bool(cfg.get("shutdown", {}).get("enabled")),
        set_fn=lambda c, on: c.async_set_shutdown_policy({"enabled": on}),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Any,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: PowerPanelCoordinator = entry.runtime_data
    async_add_entities(PowerPanelSwitch(coordinator, desc) for desc in SWITCHES)


class PowerPanelSwitch(PowerPanelEntity, SwitchEntity):
    """A single config-backed switch."""

    entity_description: PowerPanelSwitchDescription

    def __init__(
        self, coordinator: PowerPanelCoordinator, description: PowerPanelSwitchDescription
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool:
        return self.entity_description.is_on_fn(self._config)

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._set(False)

    async def _set(self, value: bool) -> None:
        try:
            await self.entity_description.set_fn(self.coordinator.client, value)
        except GatewayError as err:
            _LOGGER.error("Switch %s failed: %s", self.entity_description.key, err)
            raise
        await self.coordinator.async_request_refresh()
