# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Standalone deployment kit** (`deploy/`) for running the gateway on a machine
  other than the Home Assistant host (the common Home Assistant OS case): a
  Debian-based image (where CyberPower PowerPanel installs cleanly), a
  `docker-compose.yml` with USB passthrough and token auth, a systemd unit for
  native host installs, and a `README` covering the topology end-to-end.
- The add-on and deploy entrypoints now start the **`pwrstatd` daemon** in real
  mode (`start_pwrstatd` add-on option, default on); `pwrstat` alone is only a
  client.

### Fixed

- Add-on `Dockerfile` now gives `BUILD_FROM` a default base image, so a plain
  `docker build` works locally instead of failing on a blank base name.
- `run.sh` works without an add-on `options.json`, so the documented
  `docker run -e POWERPANEL_GATEWAY_MOCK=1` starts correctly as a plain container.

### Changed

- **Add-on re-based on the Home Assistant Debian images** (`*-base-debian`) with
  a Python venv, so CyberPower PowerPanel's glibc `.deb` installs cleanly and
  real-UPS mode works in the add-on. Drop the `.deb` into the add-on's `vendor/`
  folder and rebuild (`vendor/README.md`); the Dockerfile installs it via apt.
- Docs corrected throughout: removed the misleading "run PowerPanel on the host"
  add-on note and the now-obsolete Alpine/musl caveats; documented the `vendor/`
  drop-in flow for both the add-on and the `deploy/` image.

## [0.1.0] - 2026-06-02

### Added

- **Backend** (FastAPI): typed REST API, SSE event stream, robust `pwrstat`
  parser, mock provider, SQLite rolling event log, SMTP email alerts with
  cooldown, shutdown-policy evaluation (dry-run by default), optional bearer-token
  auth, and a secret-free diagnostics endpoint.
- **Web UI** (dependency-free, Ingress-safe): live status, events timeline with
  filtering + JSON export, email settings + test send, shutdown policy with
  "what would happen now" preview, diagnostics, and a mock-only simulator.
- **Home Assistant add-on**: `config.yaml`, multi-arch `Dockerfile`/`build.yaml`,
  `run.sh`, Ingress, options schema (mock, poll interval, email, shutdown, log
  level), USB/udev access, and docs. PowerPanel itself is user-supplied.
- **Home Assistant integration**: config + options flow, DataUpdateCoordinator,
  sensors, binary sensors, buttons, switches, services, bus events, diagnostics,
  repairs, translations, and config-entry migration scaffolding.
- **Tests**: parser, models (secret handling), emailer, REST API, and a
  HA-dependent config-flow test (auto-skipped without HA).
- **Examples**: automations and a Lovelace dashboard card; sample `pwrstat`
  outputs.
- **CI**: ruff + mypy + pytest, HA integration tests, hassfest, HACS, and
  Dockerfile lint; tag-driven release workflow.

[Unreleased]: https://github.com/hosquiat/powerpanel-gateway/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/hosquiat/powerpanel-gateway/releases/tag/v0.1.0
