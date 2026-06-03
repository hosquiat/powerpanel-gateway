"""Tests for the pwrstat parser."""

from __future__ import annotations

from pathlib import Path

import pytest

from powerpanel_gateway.models import SelfTestResult, UpsState
from powerpanel_gateway.parser import (
    is_communication_lost,
    parse_fields,
    parse_pwrstat,
    refine_low_battery,
)


def _read(fixtures_dir: Path, name: str) -> str:
    return (fixtures_dir / name).read_text(encoding="utf-8")


def test_parse_normal(fixtures_dir: Path) -> None:
    status = parse_pwrstat(_read(fixtures_dir, "normal.txt"), gateway_version="0.1.0")
    assert status.ok is True
    assert status.state is UpsState.NORMAL
    assert status.on_battery is False
    assert status.utility_power_present is True
    assert status.battery_percent == 100
    assert status.remaining_runtime_minutes == 47
    assert status.load_percent == 10
    assert status.load_watts == 86
    assert status.utility_voltage == 121.0
    assert status.output_voltage == 121.0
    assert status.model == "CP1500PFCLCD"
    assert status.last_self_test_result is SelfTestResult.PASSED
    assert status.last_power_event is None
    assert status.gateway_version == "0.1.0"


def test_parse_on_battery(fixtures_dir: Path) -> None:
    status = parse_pwrstat(_read(fixtures_dir, "on-battery.txt"))
    assert status.ok is True
    assert status.state is UpsState.ON_BATTERY
    assert status.on_battery is True
    assert status.utility_power_present is False
    assert status.battery_percent == 78
    assert status.utility_voltage == 0.0
    assert status.last_power_event is not None
    assert "Blackout" in status.last_power_event


def test_parse_low_battery_fixture(fixtures_dir: Path) -> None:
    status = parse_pwrstat(_read(fixtures_dir, "low-battery.txt"))
    assert status.on_battery is True
    assert status.battery_percent == 18
    assert status.remaining_runtime_minutes == 4


def test_parse_comm_lost(fixtures_dir: Path) -> None:
    raw = _read(fixtures_dir, "comm-lost.txt")
    assert is_communication_lost(raw) is True
    status = parse_pwrstat(raw)
    assert status.ok is False
    assert status.state is UpsState.COMMUNICATION_LOST
    assert status.error is not None


@pytest.mark.parametrize("raw", ["", "   \n  ", "garbage line\nno fields here"])
def test_parse_malformed_is_safe(raw: str) -> None:
    status = parse_pwrstat(raw)
    assert status.ok is False
    assert status.state is UpsState.COMMUNICATION_LOST


def test_parse_fields_normalizes_keys(fixtures_dir: Path) -> None:
    fields = parse_fields(_read(fixtures_dir, "normal.txt"))
    assert fields["model name"] == "CP1500PFCLCD"
    assert fields["battery capacity"] == "100 %"
    assert fields["state"] == "Normal"


def test_refine_low_battery_promotes_state() -> None:
    status = parse_pwrstat(
        "Current UPS status:\n"
        "\tState........ Power Failure\n"
        "\tPower Supply by.... Battery Power\n"
        "\tBattery Capacity.... 15 %\n"
        "\tRemaining Runtime.... 5 min.\n"
        "\tLoad.... 100 Watt(10 %)\n"
    )
    assert status.state is UpsState.ON_BATTERY
    refined = refine_low_battery(status, low_battery_percent=20, critical_battery_percent=10)
    assert refined.state is UpsState.LOW_BATTERY


def test_refine_low_battery_keeps_normal() -> None:
    status = parse_pwrstat(
        "Current UPS status:\n"
        "\tState........ Power Failure\n"
        "\tPower Supply by.... Battery Power\n"
        "\tBattery Capacity.... 80 %\n"
        "\tLoad.... 100 Watt(10 %)\n"
    )
    refined = refine_low_battery(status, low_battery_percent=20, critical_battery_percent=10)
    assert refined.state is UpsState.ON_BATTERY


def test_unknown_state_maps_to_unknown() -> None:
    status = parse_pwrstat(
        "Current UPS status:\n\tState........ Wibble\n\tBattery Capacity.... 50 %\n"
    )
    assert status.state is UpsState.UNKNOWN
