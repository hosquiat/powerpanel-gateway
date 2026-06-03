"""The PowerPanel Gateway integration."""

from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .api import GatewayError
from .const import (
    DOMAIN,
    PLATFORMS,
    SERVICE_RUN_SELF_TEST,
    SERVICE_SEND_TEST_EMAIL,
    SERVICE_SET_SHUTDOWN_POLICY,
    SERVICE_SIMULATE,
)
from .coordinator import PowerPanelCoordinator

_LOGGER = logging.getLogger(__name__)

type PowerPanelConfigEntry = ConfigEntry[PowerPanelCoordinator]

_SIMULATE_SCHEMA = vol.Schema(
    {
        vol.Required("scenario"): vol.In(
            ["normal", "power_failure", "low_battery", "power_restored", "communication_lost"]
        )
    }
)

_SET_SHUTDOWN_SCHEMA = vol.Schema(
    {
        vol.Optional("enabled"): cv.boolean,
        vol.Optional("dry_run"): cv.boolean,
        vol.Optional("shutdown_after_minutes_on_battery"): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=240)
        ),
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: PowerPanelConfigEntry) -> bool:
    """Set up PowerPanel Gateway from a config entry."""
    coordinator = PowerPanelCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _async_register_services(hass)
    entry.async_on_unload(entry.add_update_listener(_async_reload_on_update))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: PowerPanelConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    # Remove domain services when the last entry goes away.
    if unloaded and not _other_entries(hass, entry):
        for service in (
            SERVICE_RUN_SELF_TEST,
            SERVICE_SEND_TEST_EMAIL,
            SERVICE_SIMULATE,
            SERVICE_SET_SHUTDOWN_POLICY,
        ):
            hass.services.async_remove(DOMAIN, service)
    return unloaded


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old config entries to the current version."""
    if entry.version == 1:
        return True
    # Newer than we understand -> refuse rather than corrupt.
    _LOGGER.error("Unsupported config entry version %s; downgrade required", entry.version)
    return False


async def _async_reload_on_update(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


def _other_entries(hass: HomeAssistant, entry: ConfigEntry) -> list[ConfigEntry]:
    return [e for e in hass.config_entries.async_entries(DOMAIN) if e.entry_id != entry.entry_id]


def _coordinators(hass: HomeAssistant) -> list[PowerPanelCoordinator]:
    return [
        entry.runtime_data
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.state.recoverable and getattr(entry, "runtime_data", None) is not None
    ]


def _async_register_services(hass: HomeAssistant) -> None:
    """Register domain-level services once."""
    if hass.services.has_service(DOMAIN, SERVICE_RUN_SELF_TEST):
        return

    async def _for_each(action: str, call: ServiceCall) -> None:
        for coordinator in _coordinators(hass):
            client = coordinator.client
            try:
                if action == SERVICE_RUN_SELF_TEST:
                    await client.async_self_test()
                elif action == SERVICE_SEND_TEST_EMAIL:
                    await client.async_test_email()
                elif action == SERVICE_SIMULATE:
                    await client.async_simulate(call.data["scenario"])
                elif action == SERVICE_SET_SHUTDOWN_POLICY:
                    await client.async_set_shutdown_policy(dict(call.data))
            except GatewayError as err:
                _LOGGER.error("Service %s failed: %s", action, err)
            await coordinator.async_request_refresh()

    async def handle_self_test(call: ServiceCall) -> None:
        await _for_each(SERVICE_RUN_SELF_TEST, call)

    async def handle_test_email(call: ServiceCall) -> None:
        await _for_each(SERVICE_SEND_TEST_EMAIL, call)

    async def handle_simulate(call: ServiceCall) -> None:
        await _for_each(SERVICE_SIMULATE, call)

    async def handle_set_shutdown(call: ServiceCall) -> None:
        await _for_each(SERVICE_SET_SHUTDOWN_POLICY, call)

    hass.services.async_register(DOMAIN, SERVICE_RUN_SELF_TEST, handle_self_test)
    hass.services.async_register(DOMAIN, SERVICE_SEND_TEST_EMAIL, handle_test_email)
    hass.services.async_register(DOMAIN, SERVICE_SIMULATE, handle_simulate, schema=_SIMULATE_SCHEMA)
    hass.services.async_register(
        DOMAIN, SERVICE_SET_SHUTDOWN_POLICY, handle_set_shutdown, schema=_SET_SHUTDOWN_SCHEMA
    )
