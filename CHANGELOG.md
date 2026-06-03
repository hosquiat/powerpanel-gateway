# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/powerpanel-gateway/powerpanel-gateway/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/powerpanel-gateway/powerpanel-gateway/releases/tag/v0.1.0
