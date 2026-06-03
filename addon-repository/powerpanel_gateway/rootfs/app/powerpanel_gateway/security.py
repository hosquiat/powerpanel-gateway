"""Optional bearer-token authentication for the REST API.

When ``Settings.api_token`` is empty (the default for add-on / Ingress use), the
API is open on the internal port. When a token is set, every request except
``/health`` must present ``Authorization: Bearer <token>``.
"""

from __future__ import annotations

import hmac

from fastapi import HTTPException, Request, status


class TokenAuth:
    """Constant-time bearer-token checker usable as a FastAPI dependency."""

    def __init__(self, token: str) -> None:
        self._token = token

    @property
    def enabled(self) -> bool:
        return bool(self._token)

    async def __call__(self, request: Request) -> None:
        if not self.enabled:
            return
        header = request.headers.get("authorization", "")
        scheme, _, presented = header.partition(" ")
        if scheme.lower() != "bearer" or not hmac.compare_digest(presented, self._token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing API token.",
                headers={"WWW-Authenticate": "Bearer"},
            )
