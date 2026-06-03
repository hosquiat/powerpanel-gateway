"""Process settings (from the environment) and persistence of runtime config.

Two distinct concepts:

* :class:`Settings` — immutable bootstrap settings sourced from the environment
  (mock mode, data dir, bind address, log level, optional API token). These are
  fixed for the process lifetime.
* :class:`GatewayConfig` — the mutable, user-editable config (poll interval,
  email, shutdown policy). Persisted as JSON in the data dir and editable via the
  API / web UI. Defined in :mod:`powerpanel_gateway.models`.
"""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from .models import GatewayConfig

_LOGGER = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Immutable process settings sourced from ``POWERPANEL_GATEWAY_*`` env vars."""

    model_config = SettingsConfigDict(
        env_prefix="POWERPANEL_GATEWAY_",
        extra="ignore",
    )

    mock: bool = Field(default=False, description="Run with the simulated UPS provider.")
    data_dir: Path = Field(default=Path("/data"))
    host: str = "0.0.0.0"
    port: int = 8099
    log_level: str = "INFO"
    api_token: str = Field(default="", description="Optional bearer token; empty disables auth.")
    pwrstat_path: str = "pwrstat"
    pwrstat_timeout_seconds: float = 10.0

    @property
    def config_path(self) -> Path:
        return self.data_dir / "config.json"

    @property
    def events_db_path(self) -> Path:
        return self.data_dir / "events.db"

    def ensure_data_dir(self) -> None:
        """Create the data dir, falling back to a temp dir if not writable."""
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:  # pragma: no cover - environment dependent
            import tempfile

            fallback = Path(tempfile.gettempdir()) / "powerpanel-gateway"
            fallback.mkdir(parents=True, exist_ok=True)
            _LOGGER.warning("Data dir %s not usable (%s); using %s", self.data_dir, exc, fallback)
            object.__setattr__(self, "data_dir", fallback)


class ConfigStore:
    """Thread-safe load/save of :class:`GatewayConfig` as JSON.

    The store is the single source of truth for mutable config at runtime. It is
    safe to call from both the event loop (via executor) and background threads.
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()
        self._config = self._load()

    def _load(self) -> GatewayConfig:
        if not self._path.exists():
            return GatewayConfig()
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            return GatewayConfig.model_validate(data)
        except (OSError, ValueError) as exc:
            _LOGGER.error("Failed to load config from %s (%s); using defaults", self._path, exc)
            return GatewayConfig()

    @property
    def config(self) -> GatewayConfig:
        with self._lock:
            return self._config

    def save(self, config: GatewayConfig) -> GatewayConfig:
        """Persist and atomically swap in a new config."""
        with self._lock:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._path.with_suffix(".tmp")
            # mode="json" so SecretStr serializes as a string we can reload.
            payload = config.model_dump(mode="json")
            # SecretStr dumps to "**********"; preserve the real secret instead.
            payload["email"]["smtp_password"] = config.email.smtp_password.get_secret_value()
            tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            tmp.replace(self._path)
            self._config = config
            return self._config

    def update(self, partial: dict[str, object]) -> GatewayConfig:
        """Deep-merge a partial config dict over the current config and save."""
        with self._lock:
            current = self._config.model_dump(mode="json")
            current["email"]["smtp_password"] = self._config.email.smtp_password.get_secret_value()
            merged = _deep_merge(current, partial)
            new_config = GatewayConfig.model_validate(merged)
        return self.save(new_config)


def _deep_merge(base: dict[str, object], overlay: dict[str, object]) -> dict[str, object]:
    result = dict(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)  # type: ignore[arg-type]
        else:
            result[key] = value
    return result
