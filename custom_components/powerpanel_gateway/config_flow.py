"""Config and options flow for PowerPanel Gateway."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import GatewayApiClient, GatewayAuthError, GatewayConnectionError
from .const import (
    CONF_API_TOKEN,
    CONF_HOST,
    CONF_POLL_INTERVAL,
    CONF_PORT,
    CONF_SSL,
    DEFAULT_HOST,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_PORT,
    DEFAULT_SSL,
    DOMAIN,
    MAX_POLL_INTERVAL,
    MIN_POLL_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


def _user_schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=defaults.get(CONF_HOST, DEFAULT_HOST)): str,
            vol.Required(CONF_PORT, default=defaults.get(CONF_PORT, DEFAULT_PORT)): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=65535)
            ),
            vol.Optional(CONF_SSL, default=defaults.get(CONF_SSL, DEFAULT_SSL)): bool,
            vol.Optional(CONF_API_TOKEN, default=defaults.get(CONF_API_TOKEN, "")): str,
            vol.Optional(
                CONF_POLL_INTERVAL,
                default=defaults.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL),
            ): vol.All(vol.Coerce(int), vol.Range(min=MIN_POLL_INTERVAL, max=MAX_POLL_INTERVAL)),
        }
    )


async def _validate(hass: Any, data: dict[str, Any]) -> dict[str, Any]:
    """Validate connectivity; returns info for the entry title."""
    client = GatewayApiClient(
        async_get_clientsession(hass),
        data[CONF_HOST],
        data[CONF_PORT],
        use_ssl=data.get(CONF_SSL, False),
        token=data.get(CONF_API_TOKEN) or None,
    )
    health = await client.async_health()
    status = await client.async_get_status()
    return {"version": health.get("version"), "model": status.get("model")}


class PowerPanelConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for PowerPanel Gateway."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}")
            self._abort_if_unique_id_configured()
            try:
                info = await _validate(self.hass, user_input)
            except GatewayAuthError:
                errors["base"] = "invalid_auth"
            except GatewayConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error validating gateway")
                errors["base"] = "unknown"
            else:
                title = info.get("model") or f"PowerPanel Gateway ({user_input[CONF_HOST]})"
                return self.async_create_entry(title=title, data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=_user_schema(user_input or {}),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return PowerPanelOptionsFlow()


class PowerPanelOptionsFlow(OptionsFlow):
    """Options: tune poll interval and token without re-adding the entry."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = {**self.config_entry.data, **self.config_entry.options}
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_POLL_INTERVAL,
                    default=current.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL),
                ): vol.All(
                    vol.Coerce(int), vol.Range(min=MIN_POLL_INTERVAL, max=MAX_POLL_INTERVAL)
                ),
                vol.Optional(
                    CONF_API_TOKEN, default=current.get(CONF_API_TOKEN, "")
                ): str,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
