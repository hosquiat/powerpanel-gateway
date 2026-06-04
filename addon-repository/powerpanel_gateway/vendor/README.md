# vendor/ — your CyberPower PowerPanel package

This folder is where **you** place the proprietary CyberPower PowerPanel for Linux
`.deb` so the add-on can talk to a real UPS. It is empty by default (only a
`.gitkeep`), and the add-on builds/runs in **mock mode** when no `.deb` is here.

We do **not** download or redistribute PowerPanel — it is CyberPower's
proprietary software.

## How to enable real-UPS mode

1. Download "PowerPanel for Linux" (`.deb`) from CyberPower for the architecture
   your Home Assistant host runs (`amd64`, `aarch64`, or `armv7`).
2. Copy it here, e.g.:
   ```
   cp ~/Downloads/powerpanel_*_amd64.deb addon-repository/powerpanel_gateway/vendor/
   ```
3. Rebuild the add-on (Settings → Add-ons → PowerPanel Gateway → ⋮ → Rebuild).
   The Dockerfile installs every `*.deb` it finds here via `apt-get install`.
4. In the add-on config set `mock_mode: false` and keep `start_pwrstatd: true`.

Multiple `.deb` files are allowed (they're all installed). Do not commit the
`.deb` to git — it is not yours to redistribute.
