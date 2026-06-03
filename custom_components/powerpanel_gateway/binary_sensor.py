"""Binary sensor platform for PowerPanel Gateway."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import PowerPanelCoordinator
from .entity import PowerPanelEntity


@dataclass(frozen=True, kw_only=True)
class PowerPanelBinaryDescription(BinarySensorEntityDescription):
    """Binary sensor description with an is_on extractor."""

    is_on_fn: Callable[[dict[str, Any]], bool | None]


def _needs_attention(status: dict[str, Any]) -> bool:
    state = status.get("state")
    return state in {"on_battery", "low_battery", "fault", "communication_lost"} or not status.get(
        "ok", True
    )


BINARY_SENSORS: tuple[PowerPanelBinaryDescription, ...] = (
    PowerPanelBinaryDescription(
        key="ups_on_battery",
        translation_key="ups_on_battery",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        icon="mdi:battery-charging",
        is_on_fn=lambda s: bool(s.get("on_battery")),
    ),
    PowerPanelBinaryDescription(
        key="ups_low_battery",
        translation_key="ups_low_battery",
        device_class=BinarySensorDeviceClass.BATTERY,
        is_on_fn=lambda s: s.get("state") == "low_battery",
    ),
    PowerPanelBinaryDescription(
        key="ups_utility_power_present",
        translation_key="ups_utility_power_present",
        device_class=BinarySensorDeviceClass.POWER,
        is_on_fn=lambda s: bool(s.get("utility_power_present")),
    ),
    PowerPanelBinaryDescription(
        key="ups_needs_attention",
        translation_key="ups_needs_attention",
        device_class=BinarySensorDeviceClass.PROBLEM,
        is_on_fn=_needs_attention,
    ),
    PowerPanelBinaryDescription(
        key="ups_communication_ok",
        translation_key="ups_communication_ok",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        is_on_fn=lambda s: s.get("state") != "communication_lost" and bool(s.get("ok", True)),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Any,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: PowerPanelCoordinator = entry.runtime_data
    async_add_entities(PowerPanelBinarySensor(coordinator, desc) for desc in BINARY_SENSORS)


class PowerPanelBinarySensor(PowerPanelEntity, BinarySensorEntity):
    """A single UPS binary sensor."""

    entity_description: PowerPanelBinaryDescription

    def __init__(
        self, coordinator: PowerPanelCoordinator, description: PowerPanelBinaryDescription
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        return self.entity_description.is_on_fn(self._status)
