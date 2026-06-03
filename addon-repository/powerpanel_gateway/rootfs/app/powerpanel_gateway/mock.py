"""Mock UPS provider for development, CI, demos, and screenshots.

The mock renders ``pwrstat``-style text from an internal numeric model and feeds
it through the *same* parser the real provider uses, so the rest of the system
behaves identically with or without hardware. It also evolves over time (battery
drains while on battery, charges while on utility), which makes the event system
and shutdown policy demonstrable end-to-end.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from .models import ActionResult, SimulationScenario
from .pwrstat import RawResult, UpsProvider

_LOGGER = logging.getLogger(__name__)

_MODEL = "CyberPower CP1500PFCLCD"


class MockProvider(UpsProvider):
    """Simulated UPS. Drive it with :meth:`simulate`."""

    source = "mock"

    def __init__(self) -> None:
        self._scenario: SimulationScenario = "normal"
        self._battery_percent: float = 100.0
        self._load_percent: int = 12
        self._load_watts: int = 108
        self._comm_lost = False
        self._self_test_failed = False
        self._last_self_test = "Passed at 2026/05/01 12:00:03"
        self._last_power_event = "None"
        self._last_tick = datetime.now(UTC)

    # -- simulation control -------------------------------------------------

    def simulate(self, scenario: SimulationScenario) -> ActionResult:
        """Apply a simulation scenario."""
        self._scenario = scenario
        self._comm_lost = False
        now = datetime.now(UTC)

        if scenario == "normal" or scenario == "power_restored":
            self._comm_lost = False
            if scenario == "power_restored":
                self._last_power_event = f"Blackout at {self._fmt(now)}"
        elif scenario == "power_failure":
            self._last_power_event = f"Blackout at {self._fmt(now)}"
        elif scenario == "low_battery":
            self._battery_percent = min(self._battery_percent, 15.0)
            self._last_power_event = f"Blackout at {self._fmt(now)}"
        elif scenario == "communication_lost":
            self._comm_lost = True
        elif scenario == "self_test_failure":
            self._self_test_failed = True
            self._last_self_test = f"Failed at {self._fmt(now)}"

        self._last_tick = now
        return ActionResult(ok=True, message=f"Simulating scenario: {scenario}")

    @property
    def scenario(self) -> SimulationScenario:
        return self._scenario

    # -- provider interface -------------------------------------------------

    def is_available(self) -> bool:
        return True

    async def get_raw(self) -> RawResult:
        self._advance()
        if self._comm_lost:
            return RawResult(
                raw=(
                    "Failed to communicate with the UPS.\n"
                    "Please make sure the UPS is connected and pwrstatd is running."
                ),
                source=self.source,
            )
        return RawResult(raw=self._render(), source=self.source)

    async def run_self_test(self) -> ActionResult:
        now = datetime.now(UTC)
        if self._self_test_failed:
            self._last_self_test = f"Failed at {self._fmt(now)}"
            return ActionResult(ok=True, message="Self-test started (will fail in mock).")
        self._last_self_test = f"Passed at {self._fmt(now)}"
        return ActionResult(ok=True, message="Self-test started.")

    async def mute_alarm(self) -> ActionResult:
        return ActionResult(ok=True, message="Alarm muted (mock).")

    def device_info(self) -> dict[str, object]:
        return {
            "mock": True,
            "scenario": self._scenario,
            "battery_percent": round(self._battery_percent, 1),
        }

    # -- internals ----------------------------------------------------------

    def _on_battery(self) -> bool:
        return self._scenario in {"power_failure", "low_battery"}

    def _advance(self) -> None:
        """Evolve the simulated battery between calls."""
        now = datetime.now(UTC)
        elapsed_min = max(0.0, (now - self._last_tick).total_seconds() / 60.0)
        self._last_tick = now
        if self._on_battery():
            # ~3.5 %/min discharge under load.
            self._battery_percent = max(0.0, self._battery_percent - 3.5 * elapsed_min)
        else:
            # ~1.5 %/min recharge.
            self._battery_percent = min(100.0, self._battery_percent + 1.5 * elapsed_min)

    def _runtime_minutes(self) -> int:
        # Crude runtime model: full battery ~ 45 min at the simulated load.
        return max(0, round(self._battery_percent / 100.0 * 45))

    def _render(self) -> str:
        on_battery = self._on_battery()
        state = "Power Failure" if on_battery else "Normal"
        supply = "Battery Power" if on_battery else "Utility Power"
        utility_v = 0 if on_battery else 121
        output_v = 120 if on_battery else 121
        battery = round(self._battery_percent)
        runtime = self._runtime_minutes()
        return (
            "\nThe UPS information shows as following:\n\n"
            "\tProperties:\n"
            f"\t\tModel Name................... {_MODEL}\n"
            "\t\tFirmware Number............. CR01803BIA3\n"
            "\t\tRating Voltage.............. 120 V\n"
            "\t\tRating Power................ 900 Watt(1500 VA)\n\n"
            "\tCurrent UPS status:\n"
            f"\t\tState........................ {state}\n"
            f"\t\tPower Supply by.............. {supply}\n"
            f"\t\tUtility Voltage.............. {utility_v} V\n"
            f"\t\tOutput Voltage.............. {output_v} V\n"
            f"\t\tBattery Capacity............ {battery} %\n"
            f"\t\tRemaining Runtime........... {runtime} min.\n"
            f"\t\tLoad........................ {self._load_watts} Watt({self._load_percent} %)\n"
            "\t\tLine Interaction............ None\n"
            f"\t\tTest Result................. {self._last_self_test}\n"
            f"\t\tLast Power Event............ {self._last_power_event}\n"
        )

    @staticmethod
    def _fmt(dt: datetime) -> str:
        return dt.strftime("%Y/%m/%d %H:%M:%S")
