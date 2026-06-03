"""Diagnostics assembly.

Builds the :class:`~powerpanel_gateway.models.Diagnostics` payload from a live
:class:`~powerpanel_gateway.service.GatewayService`. Kept separate so the
diagnostics shape can evolve without touching the state machine.
"""

from __future__ import annotations

import platform
import sys
from typing import TYPE_CHECKING

from . import __version__
from .models import Diagnostics
from .parser import parse_fields
from .pwrstat import PwrstatProvider

if TYPE_CHECKING:
    from .service import GatewayService


def build_diagnostics(service: GatewayService) -> Diagnostics:
    """Collect a full, secret-free diagnostics snapshot."""
    raw = service.last_raw_text()
    is_pwrstat = isinstance(service.provider, PwrstatProvider)
    device_info = service.provider.device_info()
    return Diagnostics(
        gateway_version=__version__,
        mock_mode=service.mock_mode,
        pwrstat_path=str(device_info.get("pwrstat_path")) if is_pwrstat else None,
        pwrstat_available=service.provider.is_available(),
        device_info=device_info,
        status=service.status,
        raw=raw,
        parsed=parse_fields(raw),
        config=service.public_config(),
        recent_events=service.event_store.list(limit=50),
        platform={
            "python": sys.version.split()[0],
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
        },
    )
