"""Config flow tests for the Home Assistant integration.

These require Home Assistant and pytest-homeassistant-custom-component, which are
heavy and not part of the gateway's own dev dependencies. The whole module is
skipped when they are unavailable, so `pytest` stays green in the backend dev
environment while CI's HA job still exercises it.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

pytest.importorskip("homeassistant")
pytest.importorskip("pytest_homeassistant_custom_component")

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.powerpanel_gateway.const import (
    CONF_HOST,
    CONF_PORT,
    DOMAIN,
)

# Note: pytest-homeassistant-custom-component auto-registers via its entry point
# when installed, so we do NOT declare `pytest_plugins` here (pytest only honors
# that in the root conftest, and declaring it in a test module is a usage error).


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Allow loading the custom integration during tests."""
    return


async def test_user_flow_success(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with (
        patch(
            "custom_components.powerpanel_gateway.config_flow.GatewayApiClient.async_health",
            new=AsyncMock(return_value={"version": "0.1.0", "mock_mode": True}),
        ),
        patch(
            "custom_components.powerpanel_gateway.config_flow.GatewayApiClient.async_get_status",
            new=AsyncMock(return_value={"model": "CP1500PFCLCD"}),
        ),
        patch(
            "custom_components.powerpanel_gateway.async_setup_entry",
            new=AsyncMock(return_value=True),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "localhost", CONF_PORT: 8099},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_HOST] == "localhost"


async def test_user_flow_cannot_connect(hass: HomeAssistant) -> None:
    from custom_components.powerpanel_gateway.api import GatewayConnectionError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "custom_components.powerpanel_gateway.config_flow.GatewayApiClient.async_health",
        new=AsyncMock(side_effect=GatewayConnectionError("boom")),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "localhost", CONF_PORT: 8099},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
