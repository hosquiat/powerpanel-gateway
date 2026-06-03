# Security Policy

## Supported versions

This project is pre-1.0. Security fixes target the latest `0.x` release.

## Reporting a vulnerability

Please **do not** open a public issue for security problems. Instead, use GitHub's
**private vulnerability reporting** ("Report a vulnerability" under the Security
tab) for this repository. Include:

- affected component (backend / add-on / integration) and version,
- a description and, ideally, a minimal reproduction,
- impact assessment if known.

We aim to acknowledge reports within 7 days.

## Security model & hardening notes

- **Local-only by design.** The gateway requires no cloud services and makes no
  outbound connections except SMTP (only if you enable email alerts).
- **Ingress-first.** The add-on exposes the UI/API through Home Assistant Ingress
  and publishes no host port by default. If you publish port `8099`, set
  `POWERPANEL_GATEWAY_API_TOKEN` and treat the endpoint as sensitive.
- **Auth.** When a token is set, all `/api/*` routes require
  `Authorization: Bearer <token>` (constant-time comparison); `/health` stays
  open for liveness checks.
- **Secrets.** SMTP passwords are held in `SecretStr`, are never logged, never
  returned by `GET /api/config`, and are redacted from diagnostics.
- **Shutdown safety.** Host shutdown is disabled by default and additionally
  gated behind `dry_run=false`. In dry-run the gateway only reports intent.
- **Least privilege.** The add-on requests USB/udev access (not full privileged
  mode) and documents any broader access rather than enabling it by default.
- **No proprietary redistribution.** CyberPower PowerPanel is not bundled; users
  supply it themselves for real-UPS mode.
