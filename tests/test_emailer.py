"""Tests for the SMTP emailer (no real network)."""

from __future__ import annotations

import pytest

from powerpanel_gateway.emailer import Emailer
from powerpanel_gateway.models import EmailConfig, UpsState, UpsStatus


def _status() -> UpsStatus:
    return UpsStatus(
        ok=True,
        state=UpsState.ON_BATTERY,
        on_battery=True,
        battery_percent=42,
        remaining_runtime_minutes=12,
        load_percent=20,
        load_watts=180,
        model="CP1500PFCLCD",
        gateway_version="0.1.0",
    )


def _enabled_config(**overrides: object) -> EmailConfig:
    base = {
        "enabled": True,
        "smtp_host": "smtp.example.com",
        "smtp_from": "ups@example.com",
        "smtp_to": ["admin@example.com"],
        "cooldown_minutes": 15,
    }
    base.update(overrides)
    return EmailConfig(**base)  # type: ignore[arg-type]


def test_render_includes_key_fields() -> None:
    body = Emailer().render("power_failure", _status(), home_assistant_url="http://ha.local")
    assert "on_battery" in body
    assert "42 %" in body
    assert "12 min" in body
    assert "http://ha.local" in body


async def test_send_captures_message(monkeypatch: pytest.MonkeyPatch) -> None:
    emailer = Emailer()
    captured: dict[str, object] = {}

    def fake_send(config: EmailConfig, subject: str, body: str) -> None:
        captured["subject"] = subject
        captured["body"] = body
        captured["to"] = config.smtp_to

    monkeypatch.setattr(Emailer, "_smtp_send", staticmethod(fake_send))
    result = await emailer.send(_enabled_config(), "Subject", "Body")
    assert result.ok is True
    assert captured["subject"] == "Subject"
    assert captured["to"] == ["admin@example.com"]


async def test_send_missing_config_fails_cleanly() -> None:
    result = await Emailer().send(EmailConfig(enabled=True), "s", "b")
    assert result.ok is False
    assert "missing" in result.message


async def test_maybe_send_respects_disabled() -> None:
    result = await Emailer().maybe_send(EmailConfig(enabled=False), "power_failure", _status())
    assert result is None


async def test_maybe_send_respects_toggle(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Emailer, "_smtp_send", staticmethod(lambda *a, **k: None))
    cfg = _enabled_config(send_power_failure=False)
    result = await Emailer().maybe_send(cfg, "power_failure", _status())
    assert result is None


async def test_maybe_send_cooldown(monkeypatch: pytest.MonkeyPatch) -> None:
    sends = 0

    def fake_send(*args: object, **kwargs: object) -> None:
        nonlocal sends
        sends += 1

    monkeypatch.setattr(Emailer, "_smtp_send", staticmethod(fake_send))
    emailer = Emailer()
    cfg = _enabled_config(cooldown_minutes=60)
    first = await emailer.maybe_send(cfg, "power_failure", _status())
    second = await emailer.maybe_send(cfg, "power_failure", _status())
    assert first is not None and first.ok is True
    assert second is None  # suppressed by cooldown
    assert sends == 1


async def test_maybe_send_force_bypasses_everything(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Emailer, "_smtp_send", staticmethod(lambda *a, **k: None))
    result = await Emailer().maybe_send(
        EmailConfig(enabled=False, smtp_host="h", smtp_from="f@x", smtp_to=["t@x"]),
        "test",
        _status(),
        force=True,
    )
    assert result is not None and result.ok is True
