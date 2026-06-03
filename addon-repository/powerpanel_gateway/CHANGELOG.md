# Changelog

## 0.1.0

- Initial release of the PowerPanel Gateway add-on.
- Mock mode for hardware-free evaluation.
- REST API + SSE event stream on port 8099 (Ingress).
- Web UI: live status, events, email alerts, shutdown policy, diagnostics, simulator.
- SMTP email alerting with per-event toggles and cooldown.
- Shutdown policy (dry-run by default; host shutdown never enabled implicitly).
- USB/udev access for CyberPower PowerPanel; PowerPanel itself is user-supplied.
