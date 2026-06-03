"""FastAPI router: thin HTTP layer over :class:`GatewayService`.

All endpoints are async and do no blocking work themselves; the service handles
executor offloading for disk/subprocess I/O.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from collections.abc import AsyncIterator, Callable
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from . import __version__
from .models import (
    ActionResult,
    Diagnostics,
    Event,
    EventType,
    HealthResponse,
    PublicConfig,
    RawResponse,
    ShutdownEvaluation,
    SimulateRequest,
    UpsStatus,
)
from .service import GatewayService

_LOGGER = logging.getLogger(__name__)


def get_service(request: Request) -> GatewayService:
    """Dependency: pull the singleton service off app state."""
    service = getattr(request.app.state, "service", None)
    if service is None:  # pragma: no cover - misconfiguration
        raise HTTPException(status_code=503, detail="Gateway service not initialized.")
    return service


ServiceDep = Annotated[GatewayService, Depends(get_service)]


def create_router(auth_dependency: Callable[..., object]) -> APIRouter:
    """Build the API router with the given auth dependency applied to /api/*."""
    router = APIRouter()
    protected = [Depends(auth_dependency)]

    # -- health (always unauthenticated) -----------------------------------

    @router.get("/health", response_model=HealthResponse, tags=["meta"])
    async def health(service: ServiceDep) -> HealthResponse:
        return HealthResponse(version=__version__, mock_mode=service.mock_mode)

    api = APIRouter(prefix="/api", dependencies=protected)

    # -- status / raw ------------------------------------------------------

    @api.get("/status", response_model=UpsStatus, tags=["status"])
    async def get_status(service: ServiceDep) -> UpsStatus:
        return service.status

    @api.get("/raw", response_model=RawResponse, tags=["status"])
    async def get_raw(service: ServiceDep) -> RawResponse:
        return service.raw_response()

    # -- events ------------------------------------------------------------

    @api.get("/events", response_model=list[Event], tags=["events"])
    async def get_events(
        service: ServiceDep,
        limit: Annotated[int, Query(ge=1, le=1000)] = 200,
        event_type: Annotated[EventType | None, Query(alias="type")] = None,
        since: Annotated[datetime | None, Query()] = None,
    ) -> list[Event]:
        return await service.list_events(limit=limit, event_type=event_type, since=since)

    # -- config ------------------------------------------------------------

    @api.get("/config", response_model=PublicConfig, tags=["config"])
    async def get_config(service: ServiceDep) -> PublicConfig:
        return service.public_config()

    @api.post("/config", response_model=PublicConfig, tags=["config"])
    async def post_config(service: ServiceDep, request: Request) -> PublicConfig:
        try:
            partial = await request.json()
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail="Invalid JSON body.") from exc
        if not isinstance(partial, dict):
            raise HTTPException(status_code=400, detail="Body must be a JSON object.")
        loop = asyncio.get_running_loop()
        try:
            await loop.run_in_executor(None, service.config_store.update, partial)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=f"Invalid config: {exc}") from exc
        return service.public_config()

    # -- actions -----------------------------------------------------------

    @api.post("/actions/refresh", response_model=UpsStatus, tags=["actions"])
    async def action_refresh(service: ServiceDep) -> UpsStatus:
        return await service.action_refresh()

    @api.post("/actions/self-test", response_model=ActionResult, tags=["actions"])
    async def action_self_test(service: ServiceDep) -> ActionResult:
        return await service.action_self_test()

    @api.post("/actions/mute-alarm", response_model=ActionResult, tags=["actions"])
    async def action_mute_alarm(service: ServiceDep) -> ActionResult:
        return await service.action_mute_alarm()

    @api.post("/actions/test-email", response_model=ActionResult, tags=["actions"])
    async def action_test_email(service: ServiceDep) -> ActionResult:
        return await service.action_test_email()

    @api.post("/actions/simulate", response_model=ActionResult, tags=["actions"])
    async def action_simulate(service: ServiceDep, body: SimulateRequest) -> ActionResult:
        result = await service.action_simulate(body.scenario)
        if not result.ok:
            raise HTTPException(status_code=409, detail=result.message)
        return result

    # -- shutdown evaluation ----------------------------------------------

    @api.get("/shutdown/evaluate", response_model=ShutdownEvaluation, tags=["shutdown"])
    async def shutdown_evaluate(service: ServiceDep) -> ShutdownEvaluation:
        return service.evaluate_shutdown()

    # -- diagnostics -------------------------------------------------------

    @api.get("/diagnostics", response_model=Diagnostics, tags=["diagnostics"])
    async def get_diagnostics(service: ServiceDep) -> Diagnostics:
        return service.diagnostics()

    # -- event stream (SSE) ------------------------------------------------

    @api.get("/stream", tags=["events"])
    async def stream(service: ServiceDep, request: Request) -> StreamingResponse:
        return StreamingResponse(
            _sse_generator(service, request),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    router.include_router(api)
    return router


async def _sse_generator(service: GatewayService, request: Request) -> AsyncIterator[bytes]:
    """Yield server-sent events for status updates and new events."""
    queue = service.subscribe()
    # Prime the stream with the current status so clients render immediately.
    initial = json.dumps({"type": "status", "data": service.status.model_dump(mode="json")})
    yield f"data: {initial}\n\n".encode()
    try:
        while True:
            if await request.is_disconnected():
                break
            try:
                message = await asyncio.wait_for(queue.get(), timeout=15.0)
            except TimeoutError:
                # Heartbeat comment keeps proxies from closing the connection.
                yield b": ping\n\n"
                continue
            payload = json.dumps(message)
            yield f"data: {payload}\n\n".encode()
    finally:
        service.unsubscribe(queue)
        with contextlib.suppress(Exception):
            queue.get_nowait()
