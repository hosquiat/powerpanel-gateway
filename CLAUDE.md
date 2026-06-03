# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`powerpanel-gateway` is a CyberPower UPS gateway for Home Assistant. It has three
cooperating parts:

1. **Backend** — a FastAPI app that wraps CyberPower PowerPanel's `pwrstat` (or a
   mock), normalizes status into typed JSON, keeps an event log, sends email
   alerts, and evaluates a shutdown policy. Exposes REST + SSE + a web UI.
2. **Home Assistant add-on** — packages the backend as an add-on with Ingress.
3. **Home Assistant custom integration** — polls the backend API and creates
   entities/events.

## Commands

```bash
# Setup
python -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"

# Quality gate (run all three before considering work done)
ruff check .
mypy .
pytest

# Single test / single file
pytest tests/test_parser.py
pytest tests/test_api.py::test_health
pytest -k "shutdown"

# Run backend locally (mock mode = no UPS needed)
POWERPANEL_GATEWAY_MOCK=1 uvicorn powerpanel_gateway.main:app --port 8099 --reload

# Container (mock)
docker build -t powerpanel-gateway:dev ./addon-repository/powerpanel_gateway
docker run --rm -p 8099:8099 -e POWERPANEL_GATEWAY_MOCK=1 powerpanel-gateway:dev
```

The HA-dependent test (`tests/test_integration_config_flow.py`) auto-skips unless
`homeassistant` + `pytest-homeassistant-custom-component` are installed; CI runs
it in a separate job.

## Architecture & non-obvious layout

- **The Python package has one home:** `addon-repository/powerpanel_gateway/rootfs/app/powerpanel_gateway/`.
  It is *not* at the repo root. `pyproject.toml` maps it onto the import path
  (`package-dir`, `pythonpath`, `mypy_path`) so `import powerpanel_gateway` works
  for dev/tests while the same tree is what the add-on container ships.
- **Data flow:** `pwrstat.py`/`mock.py` (providers) → `parser.py` (raw text →
  `UpsStatus`) → `service.py` (state machine, events, alerts, SSE broadcast,
  shutdown eval) → `api.py` (thin HTTP) → `main.py` (app factory + static UI).
- **`service.py` is the only stateful component.** `api.py` endpoints are thin
  wrappers over a single `GatewayService` held on `app.state.service`. The state
  machine (power transitions, battery thresholds, comm-loss, self-test,
  shutdown arming) lives entirely in `service.py`. Put orchestration there, not
  in `api.py`.
- **`models.py` is the public contract.** `UpsStatus` field names/types are
  consumed directly by the integration — treat them as stable API.
- **Config split:** `config.Settings` = immutable process/env bootstrap
  (`POWERPANEL_GATEWAY_*`); `models.GatewayConfig` = mutable user config persisted
  to `${data_dir}/config.json` via `config.ConfigStore`. Don't conflate them.
- **Blocking I/O is offloaded.** Subprocess (`pwrstat`), SQLite (`events.py`),
  and SMTP (`emailer.py`) calls run via `asyncio.create_subprocess_*`,
  `run_in_executor`, or `asyncio.to_thread`. Keep the event loop non-blocking.
- **Web UI is build-free.** `web/index.html` + `app.js` + `styles.css` are served
  statically and use **relative** URLs so Home Assistant Ingress path prefixes
  work. The `web/src` + `vite.config.ts` Vite scaffold is optional and not built
  in the container.
- **Integration entities** are description-driven (`*EntityDescription` tuples in
  each platform) and share `entity.PowerPanelEntity`. The `coordinator` fetches
  status + config + shutdown-eval each cycle and re-fires gateway events on the
  HA bus (mapping in `const.GATEWAY_EVENT_TO_HA_EVENT`).

## Hard rules (safety / licensing)

- **Host shutdown stays off by default.** It runs only when `shutdown.enabled` is
  true AND `shutdown.dry_run` is false. Don't change those defaults.
- **Never log SMTP passwords** or leak secrets via `/api/config` or diagnostics.
  Passwords are `SecretStr`; keep them that way.
- **GPL-3.0-or-later.** This project derives *ideas* (not code) from the GPL
  upstreams `sbruggeman/pwrstat-api` and `twrecked/hass-pwrstat`. If you ever copy
  code from them, add the original license header + a change note at the copy
  site, and preserve attribution in README.
- **Don't bundle CyberPower PowerPanel** (proprietary) into the image.
- **Don't claim broad device support.** Only a `CP1500PFCLCD` informs the
  fixtures; a "tested devices" list is added only from real reports.

## When changing the parser

Add/adjust a fixture in `examples/sample-pwrstat-output/` and assert against it in
`tests/test_parser.py`. The parser must never raise on malformed input — return a
`communication_lost` / `unknown` status instead. Assumptions about the `pwrstat`
format live in `docs/ASSUMPTIONS.md`; update them when behavior changes.
