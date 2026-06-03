"""Typed data models shared across the gateway.

These Pydantic models are the public contract of the REST API. Keep field names
and types stable; the Home Assistant integration depends on this schema.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, SecretStr, field_validator

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class UpsState(StrEnum):
    """Normalized UPS state.

    Distinct from the raw PowerPanel ``State`` string, which is mapped onto
    these values by :mod:`powerpanel_gateway.parser`.
    """

    NORMAL = "normal"
    ON_BATTERY = "on_battery"
    LOW_BATTERY = "low_battery"
    POWER_RESTORED = "power_restored"
    SELF_TEST = "self_test"
    FAULT = "fault"
    COMMUNICATION_LOST = "communication_lost"
    UNKNOWN = "unknown"


class EventType(StrEnum):
    """Types of events recorded in the rolling event log."""

    POWER_FAILURE_STARTED = "power_failure_started"
    POWER_RESTORED = "power_restored"
    BATTERY_LOW = "battery_low"
    BATTERY_CRITICAL = "battery_critical"
    SHUTDOWN_COUNTDOWN_STARTED = "shutdown_countdown_started"
    SHUTDOWN_CANCELLED = "shutdown_cancelled"
    SELF_TEST_STARTED = "self_test_started"
    SELF_TEST_PASSED = "self_test_passed"
    SELF_TEST_FAILED = "self_test_failed"
    COMMUNICATION_LOST = "communication_lost"
    COMMUNICATION_RESTORED = "communication_restored"
    EMAIL_SENT = "email_sent"
    EMAIL_FAILED = "email_failed"


class SelfTestResult(StrEnum):
    """Result of the last UPS self test."""

    PASSED = "passed"
    FAILED = "failed"
    IN_PROGRESS = "in_progress"
    UNKNOWN = "unknown"


SimulationScenario = Literal[
    "normal",
    "power_failure",
    "low_battery",
    "power_restored",
    "communication_lost",
    "self_test_failure",
]


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------


class UpsStatus(BaseModel):
    """Normalized, typed UPS status returned by ``GET /api/status``."""

    ok: bool = Field(description="True when the gateway can talk to the UPS.")
    state: UpsState = UpsState.UNKNOWN
    on_battery: bool = False
    utility_power_present: bool = True
    battery_percent: int | None = None
    remaining_runtime_minutes: int | None = None
    load_percent: int | None = None
    load_watts: int | None = None
    utility_voltage: float | None = None
    output_voltage: float | None = None
    battery_voltage: float | None = None
    frequency_hz: float | None = None
    model: str = "unknown"
    serial_number: str = "unknown"
    last_power_event: str | None = None
    last_self_test_result: SelfTestResult = SelfTestResult.UNKNOWN
    raw_updated_at: datetime | None = None
    gateway_version: str = "0.0.0"

    # Derived helpers (not part of the documented stable schema but harmless to
    # serialize; the integration ignores unknown fields).
    error: str | None = Field(
        default=None,
        description="Human-safe error message when ok is false.",
    )


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------


class Event(BaseModel):
    """A single recorded event."""

    id: int | None = None
    type: EventType
    timestamp: datetime
    message: str = ""
    state: UpsState | None = None
    battery_percent: int | None = None
    remaining_runtime_minutes: int | None = None
    detail: dict[str, object] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class EmailConfig(BaseModel):
    """SMTP / alerting configuration.

    ``smtp_password`` is a :class:`~pydantic.SecretStr` so it is never rendered
    in logs, diagnostics, or ``GET /api/config`` responses.
    """

    enabled: bool = False
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: SecretStr = SecretStr("")
    smtp_use_tls: bool = True
    smtp_from: str = ""
    smtp_to: list[str] = Field(default_factory=list)
    cooldown_minutes: int = 15

    send_power_failure: bool = True
    send_power_restored: bool = True
    send_low_battery: bool = True
    send_shutdown_pending: bool = True
    send_comm_lost: bool = True
    send_daily_summary: bool = False

    @field_validator("smtp_to", mode="before")
    @classmethod
    def _split_recipients(cls, value: object) -> object:
        """Accept a comma/space separated string as well as a list."""
        if isinstance(value, str):
            return [part.strip() for part in value.replace(";", ",").split(",") if part.strip()]
        return value


class ShutdownConfig(BaseModel):
    """Host shutdown policy.

    SAFETY: ``dry_run`` defaults to True and host shutdown only ever runs when
    ``enabled`` is True *and* ``dry_run`` is False.
    """

    enabled: bool = False
    shutdown_after_minutes_on_battery: int = 10
    shutdown_below_battery_percent: int = 20
    shutdown_below_runtime_minutes: int = 5
    shutdown_command: str = "/sbin/poweroff"
    dry_run: bool = True


class GatewayConfig(BaseModel):
    """Mutable, persisted runtime configuration.

    Distinct from :class:`~powerpanel_gateway.config.Settings`, which holds
    immutable process/bootstrap settings sourced from the environment.
    """

    poll_interval_seconds: int = Field(default=10, ge=2, le=3600)
    low_battery_percent: int = Field(default=20, ge=1, le=99)
    critical_battery_percent: int = Field(default=10, ge=1, le=99)
    home_assistant_url: str = ""
    email: EmailConfig = Field(default_factory=EmailConfig)
    shutdown: ShutdownConfig = Field(default_factory=ShutdownConfig)


class PublicEmailConfig(BaseModel):
    """Email config without the password, safe to return over the API."""

    enabled: bool
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_password_set: bool
    smtp_use_tls: bool
    smtp_from: str
    smtp_to: list[str]
    cooldown_minutes: int
    send_power_failure: bool
    send_power_restored: bool
    send_low_battery: bool
    send_shutdown_pending: bool
    send_comm_lost: bool
    send_daily_summary: bool

    @classmethod
    def from_config(cls, cfg: EmailConfig) -> PublicEmailConfig:
        data = cfg.model_dump()
        password = data.pop("smtp_password")
        # SecretStr serializes to "**********"; check the underlying value.
        data["smtp_password_set"] = bool(cfg.smtp_password.get_secret_value())
        del password
        return cls(**data)


class PublicConfig(BaseModel):
    """Full config view returned by ``GET /api/config`` (no secrets)."""

    poll_interval_seconds: int
    low_battery_percent: int
    critical_battery_percent: int
    home_assistant_url: str
    email: PublicEmailConfig
    shutdown: ShutdownConfig
    mock_mode: bool

    @classmethod
    def from_config(cls, cfg: GatewayConfig, *, mock_mode: bool) -> PublicConfig:
        return cls(
            poll_interval_seconds=cfg.poll_interval_seconds,
            low_battery_percent=cfg.low_battery_percent,
            critical_battery_percent=cfg.critical_battery_percent,
            home_assistant_url=cfg.home_assistant_url,
            email=PublicEmailConfig.from_config(cfg.email),
            shutdown=cfg.shutdown,
            mock_mode=mock_mode,
        )


# ---------------------------------------------------------------------------
# Action / response payloads
# ---------------------------------------------------------------------------


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    version: str
    mock_mode: bool


class ActionResult(BaseModel):
    ok: bool
    message: str
    detail: dict[str, object] = Field(default_factory=dict)


class SimulateRequest(BaseModel):
    scenario: SimulationScenario


class ShutdownEvaluation(BaseModel):
    """What the shutdown policy would do given the current status."""

    would_shutdown: bool
    reason: str | None = None
    dry_run: bool
    enabled: bool
    minutes_on_battery: float | None = None
    estimated_shutdown_at: datetime | None = None


class RawResponse(BaseModel):
    raw: str
    updated_at: datetime | None = None
    source: Literal["pwrstat", "mock"]


class Diagnostics(BaseModel):
    gateway_version: str
    mock_mode: bool
    pwrstat_path: str | None = None
    pwrstat_available: bool
    device_info: dict[str, object] = Field(default_factory=dict)
    status: UpsStatus
    raw: str
    parsed: dict[str, str]
    config: PublicConfig
    recent_events: list[Event]
    platform: dict[str, str] = Field(default_factory=dict)
