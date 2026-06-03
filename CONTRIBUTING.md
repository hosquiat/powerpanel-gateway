# Contributing

Thanks for your interest in improving powerpanel-gateway!

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Run the full local check suite before opening a PR:

```bash
ruff check .
mypy .
pytest
```

Run the backend in mock mode while developing:

```bash
POWERPANEL_GATEWAY_MOCK=1 uvicorn powerpanel_gateway.main:app --port 8099 --reload
```

## Project conventions

- **Python 3.12+**, type hints everywhere; keep `mypy .` and `ruff check .` clean.
- The backend package lives at
  `addon-repository/powerpanel_gateway/rootfs/app/powerpanel_gateway/` (single
  source of truth, importable via `pyproject.toml`).
- Home Assistant code under `custom_components/` must be **async** with no
  blocking calls in the event loop (offload blocking work to executors).
- The REST status schema (`models.UpsStatus`) is a **public contract** — keep
  field names/types stable; the integration depends on them.
- **Never** log SMTP passwords or write secrets into diagnostics/`/api/config`.
- Host shutdown stays **off by default** (`enabled=false`, `dry_run=true`).

## Tests

- Parser changes must come with fixtures in
  `examples/sample-pwrstat-output/` and assertions in `tests/test_parser.py`.
- Integration (`custom_components`) tests require Home Assistant +
  `pytest-homeassistant-custom-component`; they are skipped automatically when
  those aren't installed. CI runs them in a dedicated job.

## Pull requests

- Keep PRs focused; describe behavior changes and update `CHANGELOG.md`.
- If you make an assumption about hardware/format, record it in
  `docs/ASSUMPTIONS.md`.
- By contributing, you agree your contributions are licensed under
  **GPL-3.0-or-later**. If you import code from a GPL upstream, add the original
  license header and a change note at the copy site.

## Reporting hardware results

Real-device reports are very welcome — they're how the "tested devices" list gets
built. Open an issue with your UPS model, PowerPanel version, and the output of
the **Export diagnostics** button (it is secret-free).
