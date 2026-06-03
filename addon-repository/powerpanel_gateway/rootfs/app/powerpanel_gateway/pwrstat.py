"""Real UPS provider: shells out to CyberPower PowerPanel's ``pwrstat``.

All subprocess work is async (``asyncio.create_subprocess_exec``) so the API
event loop is never blocked. Every failure mode is mapped to a safe result:

* missing ``pwrstat`` binary -> ``available=False`` + comm-lost raw text
* command timeout -> comm-lost raw text
* non-zero exit / stderr noise -> returned as raw for the parser to classify
"""

from __future__ import annotations

import asyncio
import logging
import shutil
from dataclasses import dataclass, field
from datetime import UTC, datetime

from .models import ActionResult

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class RawResult:
    """Raw provider output plus metadata."""

    raw: str
    source: str
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class UpsProvider:
    """Abstract provider interface implemented by real and mock providers."""

    source: str = "unknown"

    async def get_raw(self) -> RawResult:  # pragma: no cover - abstract
        raise NotImplementedError

    async def run_self_test(self) -> ActionResult:  # pragma: no cover - abstract
        raise NotImplementedError

    async def mute_alarm(self) -> ActionResult:  # pragma: no cover - abstract
        raise NotImplementedError

    def is_available(self) -> bool:  # pragma: no cover - abstract
        raise NotImplementedError

    def device_info(self) -> dict[str, object]:
        return {}


class PwrstatProvider(UpsProvider):
    """Talks to a real CyberPower UPS via the ``pwrstat`` CLI."""

    source = "pwrstat"

    def __init__(self, pwrstat_path: str = "pwrstat", timeout_seconds: float = 10.0) -> None:
        self._configured_path = pwrstat_path
        self._timeout = timeout_seconds

    @property
    def resolved_path(self) -> str | None:
        """Absolute path to ``pwrstat`` if it can be found, else None."""
        return shutil.which(self._configured_path) or (
            self._configured_path if "/" in self._configured_path else None
        )

    def is_available(self) -> bool:
        return self.resolved_path is not None

    async def _run(self, *args: str) -> tuple[int, str, str]:
        path = self.resolved_path
        if path is None:
            raise FileNotFoundError(self._configured_path)
        proc = await asyncio.create_subprocess_exec(
            path,
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=self._timeout)
        except TimeoutError:
            proc.kill()
            await proc.wait()
            raise
        return (
            proc.returncode or 0,
            stdout.decode(errors="replace"),
            stderr.decode(errors="replace"),
        )

    async def get_raw(self) -> RawResult:
        try:
            code, stdout, stderr = await self._run("-status")
        except FileNotFoundError:
            _LOGGER.error("pwrstat not found at %r", self._configured_path)
            return RawResult(
                raw="Failed to communicate with the UPS: pwrstat command not found.",
                source=self.source,
            )
        except TimeoutError:
            _LOGGER.warning("pwrstat -status timed out after %ss", self._timeout)
            return RawResult(
                raw="Failed to communicate with the UPS: pwrstat timed out.",
                source=self.source,
            )
        except OSError as exc:  # pragma: no cover - environment dependent
            _LOGGER.error("pwrstat -status failed: %s", exc)
            return RawResult(
                raw=f"Failed to communicate with the UPS: {exc}",
                source=self.source,
            )

        # pwrstat prints status to stdout; some builds emit warnings to stderr.
        raw = stdout if stdout.strip() else stderr
        if code != 0 and not stdout.strip():
            _LOGGER.debug("pwrstat exited %s; stderr=%s", code, stderr.strip())
        return RawResult(raw=raw, source=self.source)

    async def run_self_test(self) -> ActionResult:
        try:
            code, stdout, stderr = await self._run("-test")
        except FileNotFoundError:
            return ActionResult(ok=False, message="pwrstat command not found.")
        except TimeoutError:
            return ActionResult(ok=False, message="Self-test command timed out.")
        if code == 0:
            return ActionResult(ok=True, message="Self-test started.")
        return ActionResult(
            ok=False,
            message="Self-test could not be started.",
            detail={"stderr": stderr.strip() or stdout.strip()},
        )

    async def mute_alarm(self) -> ActionResult:
        # Not all PowerPanel builds expose alarm muting via the CLI. Attempt the
        # documented form and report gracefully if unsupported.
        try:
            code, stdout, stderr = await self._run("-mute", "on")
        except FileNotFoundError:
            return ActionResult(ok=False, message="pwrstat command not found.")
        except TimeoutError:
            return ActionResult(ok=False, message="Mute command timed out.")
        if code == 0:
            return ActionResult(ok=True, message="Alarm muted.")
        return ActionResult(
            ok=False,
            message="Alarm mute not supported by this PowerPanel version.",
            detail={"stderr": stderr.strip() or stdout.strip()},
        )

    def device_info(self) -> dict[str, object]:
        return {
            "pwrstat_path": self.resolved_path,
            "pwrstat_configured": self._configured_path,
            "timeout_seconds": self._timeout,
        }
