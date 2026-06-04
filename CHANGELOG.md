# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-06-04

First public release.

### Added

- **Backend** (FastAPI): typed REST API, SSE event stream, robust `pwrstat`
  parser, mock provider, SQLite rolling event log, SMTP email alerts with
  cooldown, shutdown-policy evaluation (dry-run by default), optional bearer-token
  auth, and a secret-free diagnostics endpoint.
- **Web UI** (dependency-free, Ingress-safe): live status, events timeline with
  filtering + JSON export, email settings + test send, shutdown policy with
  "what would happen now" preview, diagnostics, and a mock-only simulator.
- **Home Assistant add-on**: Debian-based image (so CyberPower PowerPanel's glibc
  `.deb` installs cleanly via a `vendor/` drop-in), Ingress UI, options schema
  (mock, poll interval, email, shutdown, log level, `start_pwrstatd`), and
  USB/udev access. Runs in mock mode out of the box; starts the `pwrstatd` daemon
  in real mode. PowerPanel itself is user-supplied.
- **Standalone deployment kit** (`deploy/`) for running the gateway on a machine
  other than the Home Assistant host (the common Home Assistant OS case): a
  Debian image, a `docker-compose.yml` with USB passthrough and token auth, and a
  systemd unit for native host installs, with an end-to-end topology README.
- **Home Assistant integration**: config + options flow, DataUpdateCoordinator,
  sensors, binary sensors, buttons, switches, services, bus events, diagnostics,
  repairs, translations, and config-entry migration scaffolding.
- **Brand assets** (`brand/`): mark, lockup, wordmark, generated PNGs and an
  `@2x` set for the Home Assistant brands repo. The logo is used for the add-on
  `icon.png`/`logo.png`, the web UI header + favicon, and the READMEs; the web UI
  accent uses the brand green (`#1eae8e`).
- **Examples**: automations and a Lovelace dashboard card; sample `pwrstat`
  outputs.
- **Tests**: parser, models (secret handling), emailer, REST API, and a
  HA-dependent config-flow test (auto-skipped without HA).
- **CI**: ruff + mypy + pytest, HA integration tests, hassfest, HACS, and
  Dockerfile lint; tag-driven release workflow.

### Notes

- Tested against a CyberPower **LX1100G** over USB (full status pipeline). No
  broad device-compatibility claims are made yet.
- Host shutdown is disabled by default and additionally gated behind
  `dry_run=true`; SMTP passwords are never logged or returned by the API.

[Unreleased]: https://github.com/hosquiat/powerpanel-gateway/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/hosquiat/powerpanel-gateway/releases/tag/v0.1.0
