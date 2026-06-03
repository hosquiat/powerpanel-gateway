"""SMTP email alerting.

Blocking ``smtplib`` work runs in a thread (``asyncio.to_thread``) so the event
loop is never blocked. Passwords are held in :class:`~pydantic.SecretStr` and are
never logged. A per-category cooldown prevents alert storms.
"""

from __future__ import annotations

import logging
import smtplib
import ssl
from datetime import UTC, datetime
from email.message import EmailMessage

from jinja2 import Environment, select_autoescape

from .models import ActionResult, EmailConfig, UpsStatus

_LOGGER = logging.getLogger(__name__)

# Alert categories map to the per-event toggle on EmailConfig.
TOGGLE_BY_CATEGORY: dict[str, str] = {
    "power_failure": "send_power_failure",
    "power_restored": "send_power_restored",
    "low_battery": "send_low_battery",
    "shutdown_pending": "send_shutdown_pending",
    "comm_lost": "send_comm_lost",
    "daily_summary": "send_daily_summary",
    "test": "",  # test always sends
}

_SUBJECTS: dict[str, str] = {
    "power_failure": "[UPS] Power failure - running on battery",
    "power_restored": "[UPS] Utility power restored",
    "low_battery": "[UPS] Battery low",
    "shutdown_pending": "[UPS] Shutdown pending",
    "comm_lost": "[UPS] Communication with UPS lost",
    "daily_summary": "[UPS] Daily summary",
    "test": "[UPS] Test email from powerpanel-gateway",
}

# Display values are precomputed in Python (see `render`) to keep the template
# simple and free of long inline conditionals.
_TEMPLATE = """\
powerpanel-gateway alert: {{ title }}

Current UPS state : {{ state }}
Battery           : {{ battery }}
Estimated runtime : {{ runtime }}
Load              : {{ load }}
On battery        : {{ 'yes' if status.on_battery else 'no' }}
Model             : {{ status.model }}
{% if outage_minutes is not none -%}
Outage duration   : {{ outage_minutes }} min
{% endif -%}
{% if actions -%}
Actions taken     : {{ actions }}
{% endif -%}
{% if home_assistant_url -%}
Home Assistant    : {{ home_assistant_url }}
{% endif -%}

Generated at {{ generated_at }} by powerpanel-gateway {{ status.gateway_version }}.
"""


class Emailer:
    """Renders and sends SMTP alerts with cooldown and toggle handling."""

    def __init__(self) -> None:
        self._env = Environment(autoescape=select_autoescape(enabled_extensions=()))
        self._template = self._env.from_string(_TEMPLATE)
        self._last_sent: dict[str, datetime] = {}

    def _on_cooldown(self, category: str, cooldown_minutes: int) -> bool:
        last = self._last_sent.get(category)
        if last is None:
            return False
        elapsed = (datetime.now(UTC) - last).total_seconds() / 60.0
        return elapsed < cooldown_minutes

    def render(
        self,
        category: str,
        status: UpsStatus,
        *,
        home_assistant_url: str = "",
        outage_minutes: float | None = None,
        actions: str | None = None,
    ) -> str:
        battery = f"{status.battery_percent} %" if status.battery_percent is not None else "unknown"
        runtime = (
            f"{status.remaining_runtime_minutes} min"
            if status.remaining_runtime_minutes is not None
            else "unknown"
        )
        if status.load_percent is not None:
            load = f"{status.load_percent} % ({status.load_watts or '?'} W)"
        else:
            load = "unknown"
        return self._template.render(
            title=_SUBJECTS.get(category, category),
            status=status,
            state=status.state.value,
            battery=battery,
            runtime=runtime,
            load=load,
            home_assistant_url=home_assistant_url,
            outage_minutes=round(outage_minutes) if outage_minutes is not None else None,
            actions=actions,
            generated_at=datetime.now(UTC).isoformat(),
        )

    async def maybe_send(
        self,
        config: EmailConfig,
        category: str,
        status: UpsStatus,
        *,
        home_assistant_url: str = "",
        outage_minutes: float | None = None,
        actions: str | None = None,
        force: bool = False,
    ) -> ActionResult | None:
        """Send an alert if enabled and not on cooldown. Returns None if skipped."""
        if not config.enabled and not force:
            return None
        toggle = TOGGLE_BY_CATEGORY.get(category, "")
        if toggle and not getattr(config, toggle, False) and not force:
            return None
        if not force and self._on_cooldown(category, config.cooldown_minutes):
            _LOGGER.debug("email category %s on cooldown; skipping", category)
            return None

        subject = _SUBJECTS.get(category, f"[UPS] {category}")
        body = self.render(
            category,
            status,
            home_assistant_url=home_assistant_url,
            outage_minutes=outage_minutes,
            actions=actions,
        )
        result = await self.send(config, subject, body)
        if result.ok:
            self._last_sent[category] = datetime.now(UTC)
        return result

    async def send(self, config: EmailConfig, subject: str, body: str) -> ActionResult:
        """Send a single message. Validates config; never logs the password."""
        missing = [
            name
            for name, value in (
                ("smtp_host", config.smtp_host),
                ("smtp_from", config.smtp_from),
            )
            if not value
        ]
        if not config.smtp_to:
            missing.append("smtp_to")
        if missing:
            return ActionResult(
                ok=False,
                message=f"Email not configured: missing {', '.join(missing)}.",
            )

        try:
            await self._send_blocking(config, subject, body)
        except (smtplib.SMTPException, OSError, ssl.SSLError) as exc:
            _LOGGER.error("Failed to send email to %s: %s", config.smtp_to, exc)
            return ActionResult(
                ok=False,
                message="Failed to send email.",
                detail={"error": str(exc)},
            )
        _LOGGER.info("Sent email '%s' to %s", subject, ", ".join(config.smtp_to))
        return ActionResult(ok=True, message=f"Email sent to {', '.join(config.smtp_to)}.")

    async def _send_blocking(self, config: EmailConfig, subject: str, body: str) -> None:
        import asyncio

        await asyncio.to_thread(self._smtp_send, config, subject, body)

    @staticmethod
    def _smtp_send(config: EmailConfig, subject: str, body: str) -> None:
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = config.smtp_from
        message["To"] = ", ".join(config.smtp_to)
        message.set_content(body)

        password = config.smtp_password.get_secret_value()
        context = ssl.create_default_context()

        if config.smtp_port == 465:
            with smtplib.SMTP_SSL(config.smtp_host, config.smtp_port, context=context) as server:
                if config.smtp_username:
                    server.login(config.smtp_username, password)
                server.send_message(message)
            return

        with smtplib.SMTP(config.smtp_host, config.smtp_port) as server:
            server.ehlo()
            if config.smtp_use_tls:
                server.starttls(context=context)
                server.ehlo()
            if config.smtp_username:
                server.login(config.smtp_username, password)
            server.send_message(message)
