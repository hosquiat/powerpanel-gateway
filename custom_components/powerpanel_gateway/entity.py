"""Shared base entity for PowerPanel Gateway."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_info import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import PowerPanelCoordinator


class PowerPanelEntity(CoordinatorEntity[PowerPanelCoordinator]):
    """Base class wiring entities to one gateway device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: PowerPanelCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._key = key
        entry_id = coordinator.config_entry.entry_id
        self._attr_unique_id = f"{entry_id}_{key}"

    @property
    def _status(self) -> dict[str, Any]:
        data = self.coordinator.data
        if not data:
            return {}
        # Surface the shutdown estimate alongside status for the relevant sensor.
        return {
            **data.status,
            "estimated_shutdown_at": data.shutdown.get("estimated_shutdown_at"),
        }

    @property
    def _config(self) -> dict[str, Any]:
        return self.coordinator.data.config if self.coordinator.data else {}

    @property
    def device_info(self) -> DeviceInfo:
        status = self._status
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.config_entry.entry_id)},
            name=status.get("model") or "CyberPower UPS",
            manufacturer=MANUFACTURER,
            model=status.get("model") or "UPS",
            sw_version=status.get("gateway_version"),
            configuration_url=self.coordinator.client.base_url,
        )

    @property
    def available(self) -> bool:
        return super().available and bool(self.coordinator.data)
