"""Application factory and entrypoint.

``app`` is a module-level FastAPI instance so the documented command works::

    uvicorn powerpanel_gateway.main:app --host 0.0.0.0 --port 8099

The web UI is served as static files from ``web/`` and uses *relative* URLs, so
it works unchanged behind Home Assistant Ingress (which serves the add-on under a
path prefix).
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from . import __version__
from .api import create_router
from .config import ConfigStore, Settings
from .events import EventStore
from .security import TokenAuth
from .service import GatewayService

_LOGGER = logging.getLogger(__name__)

_WEB_DIR = Path(__file__).parent / "web"


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build a fully wired FastAPI application."""
    settings = settings or Settings()
    _configure_logging(settings.log_level)
    settings.ensure_data_dir()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        config_store = ConfigStore(settings.config_path)
        event_store = EventStore(settings.events_db_path)
        service = GatewayService(settings, config_store, event_store)
        app.state.settings = settings
        app.state.service = service
        _LOGGER.info(
            "powerpanel-gateway %s starting (mock=%s, data=%s)",
            __version__,
            settings.mock,
            settings.data_dir,
        )
        await service.start()
        try:
            yield
        finally:
            await service.stop()
            _LOGGER.info("powerpanel-gateway stopped")

    app = FastAPI(
        title="powerpanel-gateway",
        version=__version__,
        description="CyberPower PowerPanel-native gateway for Home Assistant.",
        lifespan=lifespan,
    )

    auth = TokenAuth(settings.api_token)
    app.include_router(create_router(auth))

    # Serve the web UI last so explicit API routes take precedence.
    if _WEB_DIR.is_dir():
        app.mount("/", StaticFiles(directory=str(_WEB_DIR), html=True), name="web")
    else:  # pragma: no cover - only if packaging is wrong
        _LOGGER.warning("Web UI directory not found at %s", _WEB_DIR)

    return app


app = create_app()


def run() -> None:
    """Console-script entrypoint: ``powerpanel-gateway``."""
    import uvicorn

    settings = Settings()
    uvicorn.run(
        "powerpanel_gateway.main:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":  # pragma: no cover
    run()
