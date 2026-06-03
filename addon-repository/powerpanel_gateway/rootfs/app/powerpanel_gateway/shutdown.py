"""Host shutdown policy evaluation and (guarded) execution.

SAFETY MODEL
------------
Host shutdown is *never* performed unless **both** of these hold:

* ``ShutdownConfig.enabled is True``
* ``ShutdownConfig.dry_run is False``

The default config has ``enabled=False`` and ``dry_run=True``. In every other
case :func:`maybe_execute` only reports what it *would* do and returns without
touching the host.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from .models import ActionResult, ShutdownConfig, ShutdownEvaluation, UpsStatus

_LOGGER = logging.getLogger(__name__)


def evaluate(
    status: UpsStatus,
    config: ShutdownConfig,
    *,
    on_battery_since: datetime | None = None,
    now: datetime | None = None,
) -> ShutdownEvaluation:
    """Decide whether the policy would trigger a shutdown right now.

    Pure function: no side effects. ``on_battery_since`` is the timestamp the UPS
    most recently went onto battery (None if on utility).
    """
    now = now or datetime.now(UTC)

    minutes_on_battery: float | None = None
    if status.on_battery and on_battery_since is not None:
        minutes_on_battery = max(0.0, (now - on_battery_since).total_seconds() / 60.0)

    reasons: list[str] = []
    estimated_at: datetime | None = None

    if status.on_battery:
        if (
            minutes_on_battery is not None
            and minutes_on_battery >= config.shutdown_after_minutes_on_battery
        ):
            reasons.append(
                f"on battery for {minutes_on_battery:.0f} min "
                f"(>= {config.shutdown_after_minutes_on_battery})"
            )
        elif minutes_on_battery is not None and on_battery_since is not None:
            estimated_at = on_battery_since + timedelta(
                minutes=config.shutdown_after_minutes_on_battery
            )

        if (
            status.battery_percent is not None
            and status.battery_percent <= config.shutdown_below_battery_percent
        ):
            reasons.append(
                f"battery {status.battery_percent}% "
                f"(<= {config.shutdown_below_battery_percent}%)"
            )
        if (
            status.remaining_runtime_minutes is not None
            and status.remaining_runtime_minutes <= config.shutdown_below_runtime_minutes
        ):
            reasons.append(
                f"runtime {status.remaining_runtime_minutes} min "
                f"(<= {config.shutdown_below_runtime_minutes})"
            )

    would_shutdown = bool(reasons) and config.enabled
    return ShutdownEvaluation(
        would_shutdown=would_shutdown,
        reason="; ".join(reasons) if reasons else None,
        dry_run=config.dry_run,
        enabled=config.enabled,
        minutes_on_battery=minutes_on_battery,
        estimated_shutdown_at=estimated_at,
    )


async def maybe_execute(
    evaluation: ShutdownEvaluation,
    config: ShutdownConfig,
) -> ActionResult:
    """Execute the shutdown command only when policy + safety gates allow it.

    Returns an :class:`ActionResult` describing what happened (or what would have
    happened in dry-run).
    """
    if not evaluation.would_shutdown:
        return ActionResult(ok=True, message="No shutdown condition met.")

    if config.dry_run:
        msg = f"DRY-RUN: would run '{config.shutdown_command}' ({evaluation.reason})."
        _LOGGER.warning(msg)
        return ActionResult(ok=True, message=msg, detail={"dry_run": True})

    if not config.enabled:
        return ActionResult(ok=True, message="Shutdown policy disabled.")

    _LOGGER.critical(
        "Executing host shutdown: %s (%s)", config.shutdown_command, evaluation.reason
    )
    try:
        proc = await asyncio.create_subprocess_shell(
            config.shutdown_command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
    except OSError as exc:  # pragma: no cover - environment dependent
        _LOGGER.error("Shutdown command failed: %s", exc)
        return ActionResult(
            ok=False, message="Shutdown command failed.", detail={"error": str(exc)}
        )

    if proc.returncode == 0:
        return ActionResult(ok=True, message=f"Shutdown command executed: {evaluation.reason}")
    return ActionResult(
        ok=False,
        message="Shutdown command returned non-zero.",
        detail={"returncode": proc.returncode, "stderr": stderr.decode(errors="replace").strip()},
    )
