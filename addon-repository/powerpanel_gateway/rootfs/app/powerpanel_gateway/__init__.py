"""powerpanel-gateway: a CyberPower PowerPanel-native gateway.

A typed, tested REST API + event stream that wraps CyberPower PowerPanel's
``pwrstat`` command (or a mock provider) and exposes normalized UPS status for
consumption by Home Assistant and other local clients.

This project is licensed GPL-3.0-or-later. It is inspired by, but not a verbatim
copy of, ``sbruggeman/pwrstat-api`` and ``twrecked/hass-pwrstat`` (both GPL-3.0).
See README.md for attribution.
"""

from __future__ import annotations

__version__ = "0.1.0"

__all__ = ["__version__"]
