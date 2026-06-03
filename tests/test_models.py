"""Tests for the typed models, focusing on secret handling and validation."""

from __future__ import annotations

import pytest
from pydantic import SecretStr, ValidationError

from powerpanel_gateway.models import (
    EmailConfig,
    GatewayConfig,
    PublicConfig,
    PublicEmailConfig,
    UpsState,
    UpsStatus,
)


def test_email_recipients_split_from_string() -> None:
    cfg = EmailConfig.model_validate({"smtp_to": "a@example.com, b@example.com; c@example.com"})
    assert cfg.smtp_to == ["a@example.com", "b@example.com", "c@example.com"]


def test_email_password_is_secret() -> None:
    cfg = EmailConfig(smtp_password=SecretStr("hunter2"))
    # The repr / str must not leak the secret.
    assert "hunter2" not in repr(cfg)
    assert "hunter2" not in str(cfg.smtp_password)
    assert cfg.smtp_password.get_secret_value() == "hunter2"


def test_public_email_config_omits_password() -> None:
    cfg = EmailConfig(smtp_password=SecretStr("hunter2"), smtp_host="smtp.example.com")
    public = PublicEmailConfig.from_config(cfg)
    dumped = public.model_dump()
    assert "smtp_password" not in dumped
    assert dumped["smtp_password_set"] is True
    assert "hunter2" not in str(dumped)


def test_public_email_config_password_not_set() -> None:
    public = PublicEmailConfig.from_config(EmailConfig())
    assert public.model_dump()["smtp_password_set"] is False


def test_public_config_round_trip_has_no_secret() -> None:
    cfg = GatewayConfig(email=EmailConfig(smtp_password=SecretStr("topsecret")))
    public = PublicConfig.from_config(cfg, mock_mode=True)
    assert "topsecret" not in str(public.model_dump())
    assert public.mock_mode is True


def test_poll_interval_bounds() -> None:
    with pytest.raises(ValidationError):
        GatewayConfig(poll_interval_seconds=0)
    with pytest.raises(ValidationError):
        GatewayConfig(poll_interval_seconds=10_000)


def test_shutdown_defaults_are_safe() -> None:
    cfg = GatewayConfig()
    assert cfg.shutdown.enabled is False
    assert cfg.shutdown.dry_run is True


def test_status_defaults() -> None:
    status = UpsStatus(ok=False)
    assert status.state is UpsState.UNKNOWN
    assert status.serial_number == "unknown"
