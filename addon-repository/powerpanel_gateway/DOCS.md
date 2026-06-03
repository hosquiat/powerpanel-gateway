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

## Real UPS mode

CyberPower PowerPanel for Linux is **proprietary** and is **not** included in
this image. You have two supported paths:

### Option A — Build a custom image with PowerPanel

1. Download the PowerPanel for Linux package from CyberPower for your platform.
2. Place it in the add-on build context next to the `Dockerfile`.
3. Uncomment the install line in the `Dockerfile` (adjust for `.deb`/`.rpm`/tarball)
   and rebuild the add-on.
4. Set `mock_mode: false` and ensure `pwrstat_path` points at the installed binary
   (usually `pwrstat`).

### Option B — Run PowerPanel on the host

If `pwrstatd` already runs on your host and exposes `pwrstat`, you can mount it in.
This is host-specific and unsupported across all installs; Option A is preferred.

When `pwrstat` is unavailable, the gateway reports `communication_lost` rather
than crashing, and the add-on log explains how to add PowerPanel.

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
