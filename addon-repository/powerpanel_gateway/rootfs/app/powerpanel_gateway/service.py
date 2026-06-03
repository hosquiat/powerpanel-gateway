"""Gateway orchestration: polling, state machine, events, alerts, streaming.

This module ties the provider, parser, event store, emailer, and shutdown policy
together. It is the single stateful component the API depends on; everything in
:mod:`powerpanel_gateway.api` is a thin HTTP wrapper over a
:class:`GatewayService` instance.

(Not in the original file sketch, but factored out deliberately: keeping the
state machine out of ``api.py`` keeps both testable.)
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from datetime import UTC, datetime

from . import __version__
from . import shutdown as shutdown_policy
from .config import ConfigStore, Settings
from .diagnostics import build_diagnostics
from .emailer import Emailer
from .events import EventStore
from .mock import MockProvider
from .models import (
    ActionResult,
    Diagnostics,
    Event,
    EventType,
    PublicConfig,
    RawResponse,
    SelfTestResult,
    SimulationScenario,
    UpsState,
    UpsStatus,
)
from .parser import parse_pwrstat, refine_low_battery
from .pwrstat import PwrstatProvider, RawResult, UpsProvider

__all__ = ["GatewayService"]

_LOGGER = logging.getLogger(__name__)


class GatewayService:
    """Owns runtime state and coordinates all backend subsystems."""

    def __init__(
        self,
        settings: Settings,
        config_store: ConfigStore,
        event_store: EventStore,
        provider: UpsProvider | None = None,
        emailer: Emailer | None = None,
    ) -> None:
        self.settings = settings
        self.config_store = config_store
        self.event_store = event_store
        self.emailer = emailer or Emailer()
        self.provider: UpsProvider = provider or self._build_provider(settings)

        self._last_raw: RawResult | None = None
        self._status: UpsStatus = UpsStatus(ok=False, gateway_version=__version__)
        self._on_battery_since: datetime | None = None
        self._outage_started: datetime | None = None
        self._prev_self_test = SelfTestResult.UNKNOWN
        self._low_battery_flagged = False
        self._critical_battery_flagged = False
        self._shutdown_armed = False
        self._lock = asyncio.Lock()
        self._subscribers: set[asyncio.Queue[dict[str, object]]] = set()
        self._poll_task: asyncio.Task[None] | None = None

    @staticmethod
    def _build_provider(settings: Settings) -> UpsProvider:
        if settings.mock:
            _LOGGER.warning("Starting in MOCK mode; no real UPS is required.")
            return MockProvider()
        return PwrstatProvider(
            pwrstat_path=settings.pwrstat_path,
            timeout_seconds=settings.pwrstat_timeout_seconds,
        )

    @property
    def mock_mode(self) -> bool:
        return isinstance(self.provider, MockProvider)

    @property
    def status(self) -> UpsStatus:
        return self._status

    # -- lifecycle ----------------------------------------------------------

    async def start(self) -> None:
        await self.refresh()
        self._poll_task = asyncio.create_task(self._poll_loop(), name="powerpanel-poll")

    async def stop(self) -> None:
        if self._poll_task is not None:
            self._poll_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._poll_task
        await asyncio.get_running_loop().run_in_executor(None, self.event_store.close)

    async def _poll_loop(self) -> None:
        while True:
            interval = self.config_store.config.poll_interval_seconds
            await asyncio.sleep(interval)
            try:
                await self.refresh()
            except Exception:
                _LOGGER.exception("Unexpected error during poll")

    # -- core refresh + state machine --------------------------------------

    async def refresh(self) -> UpsStatus:
        """Fetch, parse, run the state machine, and broadcast. The hot path."""
        async with self._lock:
            raw = await self.provider.get_raw()
            cfg = self.config_store.config
            status = parse_pwrstat(
                raw.raw,
                gateway_version=__version__,
                source=raw.source,
                now=raw.updated_at,
            )
            status = refine_low_battery(
                status,
                low_battery_percent=cfg.low_battery_percent,
                critical_battery_percent=cfg.critical_battery_percent,
            )
            previous = self._status
            self._last_raw = raw
            self._status = status
            await self._run_state_machine(previous, status)
            await self._broadcast({"type": "status", "data": status.model_dump(mode="json")})
            return status

    async def _run_state_machine(self, previous: UpsStatus, current: UpsStatus) -> None:
        now = current.raw_updated_at or datetime.now(UTC)

        await self._detect_communication(previous, current)
        if current.state == UpsState.COMMUNICATION_LOST:
            return  # don't emit power/battery events on stale data

        await self._detect_power_transition(previous, current, now)
        await self._detect_battery_levels(current)
        await self._detect_self_test(previous, current)
        await self._evaluate_shutdown(current)

    async def _detect_communication(self, previous: UpsStatus, current: UpsStatus) -> None:
        was_lost = previous.state == UpsState.COMMUNICATION_LOST
        is_lost = current.state == UpsState.COMMUNICATION_LOST
        if is_lost and not was_lost:
            await self._emit(
                EventType.COMMUNICATION_LOST,
                "Lost communication with the UPS.",
                current,
            )
            await self._alert("comm_lost", current)
        elif was_lost and not is_lost:
            await self._emit(
                EventType.COMMUNICATION_RESTORED,
                "Communication with the UPS restored.",
                current,
            )

    async def _detect_power_transition(
        self, previous: UpsStatus, current: UpsStatus, now: datetime
    ) -> None:
        was_on_battery = previous.on_battery and previous.state != UpsState.COMMUNICATION_LOST
        if current.on_battery and not was_on_battery:
            self._on_battery_since = now
            self._outage_started = now
            self._low_battery_flagged = False
            self._critical_battery_flagged = False
            await self._emit(
                EventType.POWER_FAILURE_STARTED,
                "Utility power failed; running on battery.",
                current,
            )
            await self._alert("power_failure", current)
        elif not current.on_battery and was_on_battery:
            outage_minutes = None
            if self._outage_started is not None:
                outage_minutes = (now - self._outage_started).total_seconds() / 60.0
            await self._emit(
                EventType.POWER_RESTORED,
                "Utility power restored.",
                current,
                detail={"outage_minutes": round(outage_minutes, 2) if outage_minutes else None},
            )
            await self._alert("power_restored", current, outage_minutes=outage_minutes)
            self._on_battery_since = None
            self._outage_started = None
            self._low_battery_flagged = False
            self._critical_battery_flagged = False

    async def _detect_battery_levels(self, current: UpsStatus) -> None:
        pct = current.battery_percent
        if pct is None or not current.on_battery:
            return
        config = self.config_store.config
        if pct <= config.critical_battery_percent and not self._critical_battery_flagged:
            self._critical_battery_flagged = True
            self._low_battery_flagged = True
            await self._emit(
                EventType.BATTERY_CRITICAL,
                f"Battery critical at {pct}%.",
                current,
            )
            await self._alert("low_battery", current)
        elif pct <= config.low_battery_percent and not self._low_battery_flagged:
            self._low_battery_flagged = True
            await self._emit(EventType.BATTERY_LOW, f"Battery low at {pct}%.", current)
            await self._alert("low_battery", current)

    async def _detect_self_test(self, previous: UpsStatus, current: UpsStatus) -> None:
        if current.last_self_test_result == self._prev_self_test:
            return
        result = current.last_self_test_result
        if result == SelfTestResult.FAILED:
            await self._emit(EventType.SELF_TEST_FAILED, "UPS self-test failed.", current)
        elif result == SelfTestResult.PASSED and self._prev_self_test != SelfTestResult.UNKNOWN:
            await self._emit(EventType.SELF_TEST_PASSED, "UPS self-test passed.", current)
        elif result == SelfTestResult.IN_PROGRESS:
            await self._emit(EventType.SELF_TEST_STARTED, "UPS self-test started.", current)
        self._prev_self_test = result

    async def _evaluate_shutdown(self, current: UpsStatus) -> None:
        cfg = self.config_store.config
        evaluation = shutdown_policy.evaluate(
            current,
            cfg.shutdown,
            on_battery_since=self._on_battery_since,
        )
        if evaluation.would_shutdown and not self._shutdown_armed:
            self._shutdown_armed = True
            await self._emit(
                EventType.SHUTDOWN_COUNTDOWN_STARTED,
                f"Shutdown condition met: {evaluation.reason}",
                current,
                detail={"dry_run": evaluation.dry_run},
            )
            await self._alert("shutdown_pending", current)
            result = await shutdown_policy.maybe_execute(evaluation, cfg.shutdown)
            _LOGGER.warning("Shutdown evaluation: %s", result.message)
        elif not evaluation.would_shutdown and self._shutdown_armed:
            self._shutdown_armed = False
            await self._emit(
                EventType.SHUTDOWN_CANCELLED,
                "Shutdown condition cleared.",
                current,
            )

    def evaluate_shutdown(self) -> shutdown_policy.ShutdownEvaluation:
        return shutdown_policy.evaluate(
            self._status,
            self.config_store.config.shutdown,
            on_battery_since=self._on_battery_since,
        )

    # -- events + alerts + streaming ---------------------------------------

    async def _emit(
        self,
        event_type: EventType,
        message: str,
        status: UpsStatus,
        *,
        detail: dict[str, object] | None = None,
    ) -> Event:
        loop = asyncio.get_running_loop()
        event = await loop.run_in_executor(
            None,
            lambda: self.event_store.add(
                event_type,
                message=message,
                state=status.state,
                battery_percent=status.battery_percent,
                remaining_runtime_minutes=status.remaining_runtime_minutes,
                detail=detail or {},
            ),
        )
        await self._broadcast({"type": "event", "data": event.model_dump(mode="json")})
        return event

    async def _alert(
        self,
        category: str,
        status: UpsStatus,
        *,
        outage_minutes: float | None = None,
    ) -> None:
        cfg = self.config_store.config
        result = await self.emailer.maybe_send(
            cfg.email,
            category,
            status,
            home_assistant_url=cfg.home_assistant_url,
            outage_minutes=outage_minutes,
        )
        if result is None:
            return
        if result.ok:
            await self._emit(EventType.EMAIL_SENT, result.message, status)
        else:
            await self._emit(EventType.EMAIL_FAILED, result.message, status, detail=result.detail)

    def subscribe(self) -> asyncio.Queue[dict[str, object]]:
        queue: asyncio.Queue[dict[str, object]] = asyncio.Queue(maxsize=100)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[dict[str, object]]) -> None:
        self._subscribers.discard(queue)

    async def _broadcast(self, message: dict[str, object]) -> None:
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(message)
            except asyncio.QueueFull:
                _LOGGER.debug("dropping SSE message for a slow subscriber")

    # -- actions ------------------------------------------------------------

    async def action_refresh(self) -> UpsStatus:
        return await self.refresh()

    async def action_self_test(self) -> ActionResult:
        result = await self.provider.run_self_test()
        if result.ok:
            await self._emit(EventType.SELF_TEST_STARTED, "Self-test requested.", self._status)
        return result

    async def action_mute_alarm(self) -> ActionResult:
        return await self.provider.mute_alarm()

    async def action_test_email(self) -> ActionResult:
        cfg = self.config_store.config
        result = await self.emailer.maybe_send(cfg.email, "test", self._status, force=True)
        if result is None:
            return ActionResult(ok=False, message="Email is not configured.")
        if result.ok:
            await self._emit(EventType.EMAIL_SENT, "Test email sent.", self._status)
        else:
            await self._emit(EventType.EMAIL_FAILED, result.message, self._status)
        return result

    async def action_simulate(self, scenario: SimulationScenario) -> ActionResult:
        if not isinstance(self.provider, MockProvider):
            return ActionResult(
                ok=False,
                message="Simulation is only available in mock mode.",
            )
        result = self.provider.simulate(scenario)
        await self.refresh()
        return result

    # -- read models --------------------------------------------------------

    def last_raw_text(self) -> str:
        return self._last_raw.raw if self._last_raw else ""

    def raw_response(self) -> RawResponse:
        raw = self._last_raw
        return RawResponse(
            raw=raw.raw if raw else "",
            updated_at=raw.updated_at if raw else None,
            source="mock" if self.mock_mode else "pwrstat",
        )

    def public_config(self) -> PublicConfig:
        return PublicConfig.from_config(self.config_store.config, mock_mode=self.mock_mode)

    async def list_events(self, **kwargs: object) -> list[Event]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: self.event_store.list(**kwargs))  # type: ignore[arg-type]

    def diagnostics(self) -> Diagnostics:
        return build_diagnostics(self)
