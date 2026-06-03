# Web UI source (optional)

The gateway ships a **dependency-free, build-free** UI:

- `../index.html`
- `../app.js`
- `../styles.css`

The backend serves those files directly, so the container needs **no Node
toolchain** and the UI works behind Home Assistant Ingress out of the box.

This `src/` directory plus `../package.json` and `../vite.config.ts` are a
scaffold for anyone who wants to build a richer SPA (TypeScript, components,
etc.). If you adopt it:

1. `cd ..` and run `npm install && npm run build`.
2. Point the backend's static mount at `web/dist` (see `main.py`, `_WEB_DIR`).

Keep all API calls **relative** (e.g. `fetch("api/status")`) so Ingress path
prefixes keep working.
