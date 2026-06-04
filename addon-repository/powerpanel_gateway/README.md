<p align="center">
  <img src="logo.png" alt="PowerPanel Gateway" width="420">
</p>

# PowerPanel Gateway (Home Assistant add-on)

A CyberPower PowerPanel-native gateway for a UPS plugged into your Home Assistant
host over USB. Exposes a typed REST API, a live event stream, email alerting, and
a web UI (via Ingress). Pairs with the `powerpanel_gateway` custom integration.

## Highlights

- 🔌 Reads UPS status from CyberPower PowerPanel's `pwrstat`
- 🧪 **Mock mode** — try everything with no hardware
- 🌐 Web UI via Ingress (status, events, email, shutdown, diagnostics, simulator)
- 📨 SMTP email alerts with cooldowns
- 🛑 Safe shutdown policy (dry-run by default; never shuts down unless you opt in)
- 🏠 Companion Home Assistant integration for sensors, buttons, switches, events

## Install

1. Add this repository to Home Assistant:
   **Settings → Add-ons → Add-on Store → ⋮ → Repositories** and paste:
   `https://github.com/hosquiat/powerpanel-gateway`
2. Install **PowerPanel Gateway**.
3. (Optional) Turn **Mock mode** on to explore without a UPS.
4. Start the add-on and click **Open Web UI**.

For real-UPS mode you must add CyberPower PowerPanel to the image yourself — it is
proprietary and not redistributed here. See [DOCS.md](DOCS.md).

## License & attribution

GPL-3.0-or-later. Inspired by `sbruggeman/pwrstat-api` and `twrecked/hass-pwrstat`
(both GPL-3.0). See the repository root `README.md` for full attribution.
