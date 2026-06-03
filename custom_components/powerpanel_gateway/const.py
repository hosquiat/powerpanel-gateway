"""Constants for the PowerPanel Gateway integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "powerpanel_gateway"

# Config entry keys
CONF_HOST: Final = "host"
CONF_PORT: Final = "port"
CONF_SSL: Final = "ssl"
CONF_API_TOKEN: Final = "api_token"
CONF_POLL_INTERVAL: Final = "poll_interval_seconds"

DEFAULT_HOST: Final = "localhost"
DEFAULT_PORT: Final = 8099
DEFAULT_SSL: Final = False
DEFAULT_POLL_INTERVAL: Final = 10
MIN_POLL_INTERVAL: Final = 2
MAX_POLL_INTERVAL: Final = 3600

# Platforms provided by this integration.
PLATFORMS: Final = ["sensor", "binary_sensor", "button", "switch"]

# Home Assistant bus events fired when matching gateway events appear.
EVENT_POWER_FAILURE: Final = f"{DOMAIN}_power_failure"
EVENT_POWER_RESTORED: Final = f"{DOMAIN}_power_restored"
EVENT_LOW_BATTERY: Final = f"{DOMAIN}_low_battery"
EVENT_COMMUNICATION_LOST: Final = f"{DOMAIN}_communication_lost"
EVENT_SHUTDOWN_PENDING: Final = f"{DOMAIN}_shutdown_pending"
EVENT_SELF_TEST_FAILED: Final = f"{DOMAIN}_self_test_failed"

# Maps a gateway event "type" to the Home Assistant bus event to fire.
GATEWAY_EVENT_TO_HA_EVENT: Final[dict[str, str]] = {
    "power_failure_started": EVENT_POWER_FAILURE,
    "power_restored": EVENT_POWER_RESTORED,
    "battery_low": EVENT_LOW_BATTERY,
    "battery_critical": EVENT_LOW_BATTERY,
    "communication_lost": EVENT_COMMUNICATION_LOST,
    "shutdown_countdown_started": EVENT_SHUTDOWN_PENDING,
    "self_test_failed": EVENT_SELF_TEST_FAILED,
}

# Services
SERVICE_RUN_SELF_TEST: Final = "run_self_test"
SERVICE_SEND_TEST_EMAIL: Final = "send_test_email"
SERVICE_SIMULATE: Final = "simulate"
SERVICE_SET_SHUTDOWN_POLICY: Final = "set_shutdown_policy"

# Repair issue ids
ISSUE_CANNOT_CONNECT: Final = "cannot_connect"
ISSUE_AUTH_FAILED: Final = "auth_failed"

MANUFACTURER: Final = "CyberPower"
