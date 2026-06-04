# PowerPanel Gateway — Documentation

## What this add-on does

It runs the `powerpanel-gateway` backend inside Home Assistant. The backend reads
your CyberPower UPS status (via CyberPower PowerPanel's `pwrstat`, or a built-in
mock), normalizes it into typed JSON, records power events, can send email
alerts, and serves a web UI through Ingress. The companion `powerpanel_gateway`
custom integration consumes its REST API to create entities in Home Assistant.

## Configuration options

| Option | Description |
| --- | --- |
| `mock_mode` | Serve a simulated UPS (no hardware/PowerPanel needed). |
| `log_level` | Add-on log verbosity. |
| `poll_interval_seconds` | How often UPS status is read (2–3600). |
| `low_battery_percent` / `critical_battery_percent` | Battery thresholds for `low_battery`/critical events. |
| `home_assistant_url` | Optional link included in alert emails. |
| `api_token` | Optional bearer token to protect the REST API. Not needed for Ingress-only use. |
| `pwrstat_path` | Path to the `pwrstat` binary (real mode). |
| `email.*` | SMTP server, recipients, cooldown, and per-event toggles. |
| `shutdown.*` | Host shutdown policy. **`dry_run` is `true` by default.** |

Add-on options are applied to the gateway's persisted config on every start. Live
edits made in the web UI persist until the next add-on restart, after which the
options here are re-applied.

> The SMTP password is stored by Home Assistant as an add-on secret and is never
> written to the add-on log.

## Mock mode (recommended first run)

Set `mock_mode: true`, start the add-on, open the Web UI, and use the
**Simulator** tab to trigger power failure, low battery, restore, and comm-lost
scenarios. Everything (events, emails, shutdown preview) works end-to-end.

## Where is the UPS plugged in?

This add-on only makes sense for the real UPS when the UPS is plugged into the
**same host that runs this add-on** (i.e. your Home Assistant machine).

- **UPS on a *different* machine** (very common with Home Assistant OS): do **not**
  use this add-on for the backend. Run the gateway on the machine that has the
  UPS using the standalone deployment kit, and install only the *integration* on
  Home Assistant. See `deploy/README.md` in the repository.
- **UPS on this Home Assistant host:** continue below.

## Real UPS mode (UPS on this host)

CyberPower PowerPanel for Linux is **proprietary** and is **not** included in
this image. The add-on image is **Debian (glibc)**, so PowerPanel's `.deb`
installs cleanly — you just supply the package:

1. Download "PowerPanel for Linux" (`.deb`) from CyberPower for your Home
   Assistant host's architecture (`amd64`, `aarch64`, or `armv7`).
2. Copy it into the add-on's `vendor/` folder:
   ```
   cp ~/Downloads/powerpanel_*_amd64.deb addon-repository/powerpanel_gateway/vendor/
   ```
   (See `vendor/README.md`.) The Dockerfile installs every `*.deb` it finds there.
3. Rebuild the add-on: **Settings → Add-ons → PowerPanel Gateway → ⋮ → Rebuild**.
4. In the add-on config set `mock_mode: false` and keep `start_pwrstatd: true`
   (the add-on starts the `pwrstatd` daemon for you). Ensure `pwrstat_path` points
   at the installed binary (usually `pwrstat`).

`pwrstat` is only a client; the gateway also needs the **`pwrstatd` daemon**
running, which `start_pwrstatd` handles. When `pwrstat`/`pwrstatd` are
unavailable, the gateway reports `communication_lost` rather than crashing, and
the add-on log explains how to add PowerPanel.

> Reminder: this add-on only fits when the UPS is on **this** Home Assistant host.
> If the UPS is on a different machine, use the standalone deploy kit there
> instead (see `deploy/README.md`).

## USB access

PowerPanel's daemon talks to the UPS over a USB HID device (often
`/dev/usb/hiddev0`). The add-on requests `usb: true` plus `udev: true`, which is
sufficient on most hosts. If your host needs more, the least-bad fallback is to
add specific device nodes; full privileged mode is a last resort and is **not**
enabled by default. Document any change you make and prefer the narrowest access.

## Ports & security

- The web UI is served only through **Ingress** by default — no host port is
  published. This is the recommended, least-exposed setup.
- If you publish port `8099` to use the REST API directly from other machines,
  set an `api_token` and treat the endpoint as sensitive.

## Troubleshooting

- **Status shows `communication_lost`** — `pwrstat` isn't installed/reachable.
  Use mock mode, or add PowerPanel (Option A).
- **No emails** — check the **Email Alerts** tab, click *Send test email*, and
  verify SMTP host/port/credentials and that the relevant toggle is enabled.
- **Shutdown never fires** — by design while `dry_run` is on. The Shutdown tab's
  *What would happen now* preview shows the evaluation.
