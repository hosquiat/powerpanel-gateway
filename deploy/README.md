# Standalone deployment (UPS on a separate machine)

Use this when your CyberPower UPS is **not** plugged into your Home Assistant
host — for example, you run **Home Assistant OS** (where you can't install
software on the host) and the UPS is on a different Linux box.

```
CyberPower UPS ──USB──> [this machine]
                          pwrstatd + powerpanel-gateway backend
                          http://<this-machine-ip>:8099  (token-protected)
                                  │ network
                                  ▼
                        [HAOS] powerpanel_gateway integration
```

On Home Assistant you install **only the integration** (HACS or manual) and point
it at `http://<this-machine-ip>:8099` with the API token you set below. You do
**not** install the add-on, and you do **not** install anything on the HAOS host.

> Why not the add-on for this? The add-on image is Alpine (musl). CyberPower
> PowerPanel ships **glibc** binaries that won't run there. The images/units in
> this folder are Debian-based / native, where PowerPanel installs cleanly.

## Option 1 — Docker (recommended)

1. **Get PowerPanel.** Download CyberPower PowerPanel for Linux (`.deb`) for this
   machine's architecture from CyberPower. Put it in `deploy/vendor/`:
   ```
   cp ~/Downloads/powerpanel_*.deb deploy/vendor/
   ```
   (Skip this to run in mock mode.)

2. **Set a token and start it** (from the repo root or this folder):
   ```bash
   cd deploy
   export POWERPANEL_GATEWAY_API_TOKEN="$(openssl rand -hex 24)"
   echo "Token: $POWERPANEL_GATEWAY_API_TOKEN"   # save this for Home Assistant
   docker compose up -d --build
   ```

3. **Check it:**
   ```bash
   curl -s localhost:8099/health
   curl -s -H "Authorization: Bearer $POWERPANEL_GATEWAY_API_TOKEN" \
        localhost:8099/api/status
   ```

4. **Find the right USB device.** If status shows `communication_lost`, confirm
   the UPS node and adjust `devices:` in `docker-compose.yml`:
   ```bash
   lsusb | grep -i cyber
   ls -l /dev/usb/hiddev*
   ```
   As a last resort, uncomment `privileged: true`.

### Mock mode (validate the whole pipe without a UPS)

```bash
POWERPANEL_GATEWAY_MOCK=1 docker compose up -d --build
```

## Option 2 — Native host install (systemd, no Docker)

Best if PowerPanel is already installed and working on this machine
(`pwrstat -status` returns data). See the header of
[`systemd/powerpanel-gateway.service`](systemd/powerpanel-gateway.service) for
step-by-step instructions. In short: install PowerPanel, `pip install
powerpanel-gateway` into a venv, drop an env file with your token, and enable the
unit. It orders itself after CyberPower's `pwrstatd.service`.

## Connect Home Assistant

1. Install the **PowerPanel Gateway** integration on HAOS (HACS custom repo, or
   copy `custom_components/powerpanel_gateway` into `config/custom_components`).
2. **Settings → Devices & Services → Add Integration → PowerPanel Gateway.**
3. Enter:
   - **Host:** the IP of this machine
   - **Port:** `8099`
   - **API token:** the token you generated
   - leave **Use HTTPS** off unless you put a reverse proxy in front

## Security

You're exposing the API on the LAN (no Ingress here), so **always set
`POWERPANEL_GATEWAY_API_TOKEN`**. Keep the port on a trusted network or behind a
reverse proxy with TLS. SMTP passwords are never logged or returned by the API.
