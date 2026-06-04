# Changelog

## 0.1.0

- Initial release of the PowerPanel Gateway add-on.
- Mock mode for hardware-free evaluation.
- REST API + SSE event stream on port 8099 (Ingress).
- Web UI: live status, events, email alerts, shutdown policy, diagnostics, simulator.
- SMTP email alerting with per-event toggles and cooldown.
- Shutdown policy (dry-run by default; host shutdown never enabled implicitly).
- Debian-based image so CyberPower PowerPanel's `.deb` installs cleanly: drop it
  into the add-on `vendor/` folder and rebuild (see DOCS → "Real UPS mode").
- Starts the `pwrstatd` daemon in real mode (`start_pwrstatd` option, default on).
- USB/udev access for the UPS; PowerPanel itself is user-supplied.
