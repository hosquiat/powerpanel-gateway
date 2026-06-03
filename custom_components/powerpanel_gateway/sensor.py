"""Sensor platform for PowerPanel Gateway."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    UnitOfElectricPotential,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import PowerPanelCoordinator
from .entity import PowerPanelEntity


@dataclass(frozen=True, kw_only=True)
class PowerPanelSensorDescription(SensorEntityDescription):
    """Sensor description with a value extractor over the status dict."""

    value_fn: Callable[[dict[str, Any]], Any]


def _shutdown_time(status: dict[str, Any]) -> datetime | None:
    raw = status.get("estimated_shutdown_at")
    if not raw:
        return None
    return dt_util.parse_datetime(raw)


SENSORS: tuple[PowerPanelSensorDescription, ...] = (
    PowerPanelSensorDescription(
        key="ups_state",
        translation_key="ups_state",
        icon="mdi:power-plug-battery",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "normal",
            "on_battery",
            "low_battery",
            "power_restored",
            "self_test",
            "fault",
            "communication_lost",
            "unknown",
        ],
        value_fn=lambda s: s.get("state"),
    ),
    PowerPanelSensorDescription(
        key="ups_battery_capacity",
        translation_key="ups_battery_capacity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: s.get("battery_percent"),
    ),
    PowerPanelSensorDescription(
        key="ups_remaining_runtime",
        translation_key="ups_remaining_runtime",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:timer-sand",
        value_fn=lambda s: s.get("remaining_runtime_minutes"),
    ),
    PowerPanelSensorDescription(
        key="ups_load_percent",
        translation_key="ups_load_percent",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:gauge",
        value_fn=lambda s: s.get("load_percent"),
    ),
    PowerPanelSensorDescription(
        key="ups_load_watts",
        translation_key="ups_load_watts",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: s.get("load_watts"),
    ),
    PowerPanelSensorDescription(
        key="ups_utility_voltage",
        translation_key="ups_utility_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: s.get("utility_voltage"),
    ),
    PowerPanelSensorDescription(
        key="ups_output_voltage",
        translation_key="ups_output_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: s.get("output_voltage"),
    ),
    PowerPanelSensorDescription(
        key="ups_battery_voltage",
        translation_key="ups_battery_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda s: s.get("battery_voltage"),
    ),
    PowerPanelSensorDescription(
        key="ups_frequency",
        translation_key="ups_frequency",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda s: s.get("frequency_hz"),
    ),
    PowerPanelSensorDescription(
        key="ups_last_power_event",
        translation_key="ups_last_power_event",
        icon="mdi:history",
        value_fn=lambda s: s.get("last_power_event"),
    ),
    PowerPanelSensorDescription(
        key="ups_last_self_test_result",
        translation_key="ups_last_self_test_result",
        icon="mdi:test-tube",
        value_fn=lambda s: s.get("last_self_test_result"),
    ),
    PowerPanelSensorDescription(
        key="ups_estimated_shutdown_time",
        translation_key="ups_estimated_shutdown_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:power-off",
        entity_registry_enabled_default=False,
        value_fn=_shutdown_time,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Any,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: PowerPanelCoordinator = entry.runtime_data
    async_add_entities(PowerPanelSensor(coordinator, desc) for desc in SENSORS)


class PowerPanelSensor(PowerPanelEntity, SensorEntity):
    """A single UPS sensor."""

    entity_description: PowerPanelSensorDescription

    def __init__(
        self, coordinator: PowerPanelCoordinator, description: PowerPanelSensorDescription
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self._status)
