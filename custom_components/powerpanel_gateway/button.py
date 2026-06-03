"""Button platform for PowerPanel Gateway."""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.components.persistent_notification import async_create as notify
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import GatewayApiClient, GatewayError
from .const import DOMAIN
from .coordinator import PowerPanelCoordinator
from .entity import PowerPanelEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class PowerPanelButtonDescription(ButtonEntityDescription):
    """Button description with an async press action."""

    press_fn: Callable[[GatewayApiClient], Awaitable[Any]]
    notify_result: bool = False


BUTTONS: tuple[PowerPanelButtonDescription, ...] = (
    PowerPanelButtonDescription(
        key="ups_refresh_status",
        translation_key="ups_refresh_status",
        icon="mdi:refresh",
        press_fn=lambda c: c.async_refresh(),
    ),
    PowerPanelButtonDescription(
        key="ups_run_self_test",
        translation_key="ups_run_self_test",
        icon="mdi:test-tube",
        press_fn=lambda c: c.async_self_test(),
    ),
    PowerPanelButtonDescription(
        key="ups_test_email",
        translation_key="ups_test_email",
        icon="mdi:email-fast",
        press_fn=lambda c: c.async_test_email(),
    ),
    PowerPanelButtonDescription(
        key="ups_export_diagnostics",
        translation_key="ups_export_diagnostics",
        icon="mdi:download",
        press_fn=lambda c: c.async_get_diagnostics(),
        notify_result=True,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Any,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: PowerPanelCoordinator = entry.runtime_data
    async_add_entities(PowerPanelButton(coordinator, desc) for desc in BUTTONS)


class PowerPanelButton(PowerPanelEntity, ButtonEntity):
    """A single UPS button."""

    entity_description: PowerPanelButtonDescription

    def __init__(
        self, coordinator: PowerPanelCoordinator, description: PowerPanelButtonDescription
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    async def async_press(self) -> None:
        try:
            result = await self.entity_description.press_fn(self.coordinator.client)
        except GatewayError as err:
            _LOGGER.error("Button %s failed: %s", self.entity_description.key, err)
            raise
        if self.entity_description.notify_result and result is not None:
            notify(
                self.hass,
                f"```json\n{json.dumps(result, indent=2)[:8000]}\n```",
                title="PowerPanel Gateway diagnostics",
                notification_id=f"{DOMAIN}_diagnostics",
            )
        await self.coordinator.async_request_refresh()
