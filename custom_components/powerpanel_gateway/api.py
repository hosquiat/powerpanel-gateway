"""Async HTTP client for the powerpanel-gateway REST API."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
from aiohttp import ClientError, ClientResponseError, ClientTimeout

_LOGGER = logging.getLogger(__name__)

_TIMEOUT = ClientTimeout(total=15)


class GatewayError(Exception):
    """Base error for gateway communication."""


class GatewayConnectionError(GatewayError):
    """Could not reach the gateway."""


class GatewayAuthError(GatewayError):
    """Authentication with the gateway failed."""


class GatewayApiClient:
    """Thin async wrapper over the gateway REST API."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        host: str,
        port: int,
        *,
        use_ssl: bool = False,
        token: str | None = None,
    ) -> None:
        self._session = session
        scheme = "https" if use_ssl else "http"
        self._base = f"{scheme}://{host}:{port}"
        self._headers: dict[str, str] = {}
        if token:
            self._headers["Authorization"] = f"Bearer {token}"

    @property
    def base_url(self) -> str:
        return self._base

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: Any | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        url = f"{self._base}{path}"
        try:
            async with self._session.request(
                method,
                url,
                json=json,
                params=params,
                headers=self._headers,
                timeout=_TIMEOUT,
            ) as resp:
                if resp.status in (401, 403):
                    raise GatewayAuthError(f"Auth failed ({resp.status}) for {path}")
                resp.raise_for_status()
                if resp.content_type == "application/json":
                    return await resp.json()
                return await resp.text()
        except GatewayAuthError:
            raise
        except ClientResponseError as err:
            raise GatewayConnectionError(f"HTTP {err.status} for {path}") from err
        except (ClientError, TimeoutError) as err:
            raise GatewayConnectionError(f"Cannot reach gateway at {url}: {err}") from err

    # -- reads --------------------------------------------------------------

    async def async_health(self) -> dict[str, Any]:
        return await self._request("GET", "/health")

    async def async_get_status(self) -> dict[str, Any]:
        return await self._request("GET", "/api/status")

    async def async_get_config(self) -> dict[str, Any]:
        return await self._request("GET", "/api/config")

    async def async_get_events(self, *, limit: int = 50) -> list[dict[str, Any]]:
        return await self._request("GET", "/api/events", params={"limit": limit})

    async def async_get_diagnostics(self) -> dict[str, Any]:
        return await self._request("GET", "/api/diagnostics")

    async def async_evaluate_shutdown(self) -> dict[str, Any]:
        return await self._request("GET", "/api/shutdown/evaluate")

    # -- writes / actions ---------------------------------------------------

    async def async_set_config(self, partial: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", "/api/config", json=partial)

    async def async_refresh(self) -> dict[str, Any]:
        return await self._request("POST", "/api/actions/refresh")

    async def async_self_test(self) -> dict[str, Any]:
        return await self._request("POST", "/api/actions/self-test")

    async def async_test_email(self) -> dict[str, Any]:
        return await self._request("POST", "/api/actions/test-email")

    async def async_mute_alarm(self) -> dict[str, Any]:
        return await self._request("POST", "/api/actions/mute-alarm")

    async def async_simulate(self, scenario: str) -> dict[str, Any]:
        return await self._request(
            "POST", "/api/actions/simulate", json={"scenario": scenario}
        )

    async def async_set_email_enabled(self, enabled: bool) -> dict[str, Any]:
        return await self.async_set_config({"email": {"enabled": enabled}})

    async def async_set_shutdown_policy(self, policy: dict[str, Any]) -> dict[str, Any]:
        return await self.async_set_config({"shutdown": policy})
