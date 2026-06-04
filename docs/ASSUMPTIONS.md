# Assumptions

This document records the assumptions made while building `powerpanel-gateway`.
They are explicit on purpose: where the real world disagrees with an assumption,
this is the first place to look.

## pwrstat output format

- The parser targets the human-readable output of `pwrstat -status` from
  CyberPower PowerPanel for Linux. Output is a two-section, key-dotted-value
  layout (`Properties:` and `Current UPS status:`). Field labels are matched by
  normalizing the dotted leader and whitespace, so minor spacing/dot-count
  differences across PowerPanel versions are tolerated.
- Numeric fields carry units inline (`121 V`, `47 min.`, `86 Watt(10 %)`). The
  parser extracts the first number for each and treats load as both watts and a
  percentage when the `Watt(NN %)` form is present.
- Not every PowerPanel build reports every field. Missing fields parse to
  `None` rather than raising. `serial_number` is frequently unavailable and
  defaults to `"unknown"`.
- `State` strings observed: `Normal`, `Power Failure`. Other documented states
  are mapped defensively (see `parser.py` `STATE_MAP`). Unknown strings map to
  `state = "unknown"` while preserving the raw value in diagnostics.

## Devices

- We do **not** claim support for every CyberPower model. The only device the
  sample fixtures are derived from is a `CP1500PFCLCD`. A "tested devices" list
  will be added to the README only once real-hardware test reports exist.

## PowerPanel distribution

- CyberPower PowerPanel for Linux is **proprietary** and is **not** redistributed
  in this repository or its container image. The add-on/image expects the user
  to supply the `.deb`/`.rpm`/tarball, or to run in mock mode. See
  `addon-repository/powerpanel_gateway/DOCS.md`.
- PowerPanel is **two** components: the `pwrstatd` daemon (owns the USB link) and
  the `pwrstat` CLI (a client of the daemon). Real mode requires **both** to be
  running. The standalone deploy image and the add-on start `pwrstatd` for you;
  the host/systemd path relies on CyberPower's own `pwrstatd.service`.
- PowerPanel binaries are built for **glibc**. Both the Home Assistant add-on and
  the `deploy/` image are therefore **Debian-based** so the PowerPanel `.deb`
  installs cleanly; the user supplies the `.deb` via a `vendor/` folder.

## Where the UPS is connected

- The gateway must run on the host that physically has the UPS on USB. When that
  host is **not** the Home Assistant machine (common with Home Assistant OS), the
  backend runs on the UPS machine and the Home Assistant integration connects to
  it over the network (with an API token). The add-on is only appropriate when
  the UPS is on the Home Assistant host itself.

## USB access

- PowerPanel's `pwrstatd` daemon talks to the UPS over a USB HID device
  (commonly `/dev/usb/hiddev0`). The exact node varies by host. The add-on
  requests the minimum access we believe is needed and documents the privileged
  fallback rather than enabling it by default.

## Shutdown safety

- Host shutdown is **never** performed unless the user explicitly sets
  `shutdown.enabled = true` **and** `shutdown.dry_run = false`. The default
  configuration is `enabled = false`, `dry_run = true`. In dry-run the gateway
  only reports whether a shutdown *would* fire.

## Time

- All timestamps emitted by the API are timezone-aware UTC in ISO-8601 with a
  trailing `Z`. pwrstat-reported event timestamps are parsed in the host's local
  time as printed by pwrstat and converted to UTC on a best-effort basis; if the
  format is unrecognized the raw string is preserved.

## Authentication

- The REST API supports an optional bearer token. When unset (the default for
  the add-on, which is reached only via Home Assistant Ingress), the API is
  unauthenticated on the internal port. Operators exposing the port directly
  should set a token. Ingress provides the network-level protection in the
  add-on case.

## Event storage

- Events are stored in SQLite at `${POWERPANEL_GATEWAY_DATA_DIR}/events.db`
  (default `/data` in the add-on). The log is rolling: the most recent
  `events.max_rows` (default 1000) are retained.
