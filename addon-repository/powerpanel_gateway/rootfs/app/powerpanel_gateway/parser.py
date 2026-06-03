"""Parser for CyberPower PowerPanel ``pwrstat -status`` output.

Clean-room reimplementation: the field-extraction approach here is based on the
public, human-readable format of the ``pwrstat`` command and on the sample
fixtures in ``examples/sample-pwrstat-output``. It does not copy code from the
upstream GPL projects.

The parser is intentionally forgiving:

* Field labels are matched after normalizing the dotted leaders and whitespace,
  so minor formatting differences between PowerPanel versions are tolerated.
* Missing fields become ``None`` rather than raising.
* Communication failures are detected and surface as a distinct state instead of
  producing a half-empty status.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from .models import SelfTestResult, UpsState, UpsStatus

# A "key....value" line. Three or more dots act as the leader between the field
# label and its value.
_LINE_RE = re.compile(r"^\s*(?P<key>.+?)\s*\.{2,}\s*(?P<val>.*?)\s*$")

# First signed/decimal number in a string, e.g. "121 V" -> 121, "47 min." -> 47.
_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")

# Load is reported as "86 Watt(10 %)".
_LOAD_RE = re.compile(r"(?P<watts>\d+)\s*Watt\s*\(\s*(?P<percent>\d+)\s*%\s*\)", re.IGNORECASE)

# Phrases that indicate pwrstat could not reach the UPS / daemon.
_COMM_LOST_MARKERS = (
    "failed to communicate",
    "unable to communicate",
    "ups is not connected",
    "no ups",
    "cannot find",
    "is not running",
    "permission denied",
)

# Normalized raw State -> normalized UpsState.
STATE_MAP: dict[str, UpsState] = {
    "normal": UpsState.NORMAL,
    "power failure": UpsState.ON_BATTERY,
    "on battery": UpsState.ON_BATTERY,
    "battery power": UpsState.ON_BATTERY,
    "battery": UpsState.ON_BATTERY,
    "self test": UpsState.SELF_TEST,
    "self-test": UpsState.SELF_TEST,
    "fault": UpsState.FAULT,
    "overload": UpsState.FAULT,
    "bypass": UpsState.FAULT,
}


def _normalize_key(key: str) -> str:
    """Collapse whitespace and strip trailing dots from a field label."""
    return re.sub(r"\s+", " ", key).strip().rstrip(".").strip().lower()


def parse_fields(raw: str) -> dict[str, str]:
    """Return the raw label -> value mapping (normalized keys, raw values)."""
    fields: dict[str, str] = {}
    for line in raw.splitlines():
        match = _LINE_RE.match(line)
        if not match:
            continue
        key = _normalize_key(match.group("key"))
        value = match.group("val").strip()
        if key:
            fields[key] = value
    return fields


def is_communication_lost(raw: str) -> bool:
    """True when the output indicates the UPS/daemon could not be reached."""
    lowered = raw.lower()
    if any(marker in lowered for marker in _COMM_LOST_MARKERS):
        return True
    # A healthy response always contains the status section header.
    return "current ups status" not in lowered and "battery capacity" not in lowered


def _first_number(value: str | None) -> float | None:
    if not value:
        return None
    match = _NUMBER_RE.search(value)
    return float(match.group()) if match else None


def _to_int(value: float | None) -> int | None:
    return round(value) if value is not None else None


def _parse_self_test(value: str | None) -> SelfTestResult:
    if not value:
        return SelfTestResult.UNKNOWN
    lowered = value.lower()
    if "pass" in lowered:
        return SelfTestResult.PASSED
    if "fail" in lowered:
        return SelfTestResult.FAILED
    if "progress" in lowered or "testing" in lowered:
        return SelfTestResult.IN_PROGRESS
    return SelfTestResult.UNKNOWN


def _parse_last_power_event(value: str | None) -> str | None:
    if not value:
        return None
    if value.strip().lower() in {"none", "n/a", "-"}:
        return None
    return value.strip()


class CommunicationLostError(RuntimeError):
    """Raised by callers that prefer an exception over a comm-lost status."""


def parse_pwrstat(
    raw: str,
    *,
    gateway_version: str = "0.0.0",
    source: str = "pwrstat",
    now: datetime | None = None,
) -> UpsStatus:
    """Parse ``pwrstat -status`` output into a normalized :class:`UpsStatus`.

    Never raises on malformed input: unrecognized or empty output yields a
    status with ``ok=False`` and an appropriate state.
    """
    now = now or datetime.now(UTC)

    if not raw or not raw.strip():
        return UpsStatus(
            ok=False,
            state=UpsState.COMMUNICATION_LOST,
            on_battery=False,
            utility_power_present=False,
            gateway_version=gateway_version,
            raw_updated_at=now,
            error="No output received from pwrstat.",
        )

    if is_communication_lost(raw):
        return UpsStatus(
            ok=False,
            state=UpsState.COMMUNICATION_LOST,
            on_battery=False,
            utility_power_present=False,
            gateway_version=gateway_version,
            raw_updated_at=now,
            error="Could not communicate with the UPS (is pwrstatd running?).",
        )

    fields = parse_fields(raw)

    raw_state = fields.get("state", "")
    state = STATE_MAP.get(_normalize_key(raw_state), UpsState.UNKNOWN)

    power_source = fields.get("power supply by", "").lower()
    on_battery = state == UpsState.ON_BATTERY or "battery" in power_source
    utility_present = not on_battery
    if "utility" in power_source:
        utility_present = True

    battery_percent = _to_int(_first_number(fields.get("battery capacity")))
    remaining = _to_int(_first_number(fields.get("remaining runtime")))

    load_watts: int | None = None
    load_percent: int | None = None
    load_raw = fields.get("load")
    if load_raw:
        load_match = _LOAD_RE.search(load_raw)
        if load_match:
            load_watts = int(load_match.group("watts"))
            load_percent = int(load_match.group("percent"))
        else:
            load_watts = _to_int(_first_number(load_raw))

    frequency = _first_number(fields.get("output frequency") or fields.get("frequency"))

    status = UpsStatus(
        ok=True,
        state=state,
        on_battery=on_battery,
        utility_power_present=utility_present,
        battery_percent=battery_percent,
        remaining_runtime_minutes=remaining,
        load_percent=load_percent,
        load_watts=load_watts,
        utility_voltage=_first_number(fields.get("utility voltage")),
        output_voltage=_first_number(fields.get("output voltage")),
        battery_voltage=_first_number(fields.get("battery voltage")),
        frequency_hz=frequency,
        model=fields.get("model name") or "unknown",
        serial_number=fields.get("serial number") or "unknown",
        last_power_event=_parse_last_power_event(fields.get("last power event")),
        last_self_test_result=_parse_self_test(fields.get("test result")),
        raw_updated_at=now,
        gateway_version=gateway_version,
    )
    return status


def refine_low_battery(
    status: UpsStatus,
    *,
    low_battery_percent: int,
    critical_battery_percent: int,
) -> UpsStatus:
    """Upgrade an on-battery status to ``low_battery`` based on thresholds.

    pwrstat itself does not emit a distinct "low battery" state, so the gateway
    derives it from the battery percentage and configured thresholds.
    """
    if status.state != UpsState.ON_BATTERY:
        return status
    pct = status.battery_percent
    if pct is None:
        return status
    if pct <= low_battery_percent:
        return status.model_copy(update={"state": UpsState.LOW_BATTERY})
    return status
