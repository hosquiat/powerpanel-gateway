#!/usr/bin/env bash
# Entrypoint for the standalone deploy image (no bashio / no add-on options).
# Configuration comes entirely from POWERPANEL_GATEWAY_* environment variables.
set -euo pipefail

export POWERPANEL_GATEWAY_HOST="0.0.0.0"
export POWERPANEL_GATEWAY_PORT="${POWERPANEL_GATEWAY_PORT:-8099}"
export POWERPANEL_GATEWAY_DATA_DIR="${POWERPANEL_GATEWAY_DATA_DIR:-/data}"
mkdir -p "${POWERPANEL_GATEWAY_DATA_DIR}"

MOCK="${POWERPANEL_GATEWAY_MOCK:-0}"

if [ "${MOCK}" = "1" ] || [ "${MOCK}" = "true" ]; then
    echo "[run] Starting in MOCK mode (no real UPS required)."
else
    if command -v pwrstatd >/dev/null 2>&1; then
        # pwrstat is only a client; pwrstatd owns the USB link to the UPS.
        echo "[run] Starting pwrstatd daemon..."
        pwrstatd || echo "[run] WARNING: pwrstatd failed to start; check USB access/--device."
        sleep 2
    else
        echo "[run] WARNING: pwrstatd not found. Real mode needs CyberPower PowerPanel."
        echo "[run] Put your PowerPanel .deb in deploy/vendor/ and rebuild, or set"
        echo "[run] POWERPANEL_GATEWAY_MOCK=1. The gateway will report 'communication_lost'."
    fi
fi

LOG_LEVEL="$(echo "${POWERPANEL_GATEWAY_LOG_LEVEL:-info}" | tr '[:upper:]' '[:lower:]')"
case "${LOG_LEVEL}" in
    trace|debug|info|warning|error|critical) : ;;
    notice) LOG_LEVEL="info" ;;
    fatal) LOG_LEVEL="critical" ;;
    *) LOG_LEVEL="info" ;;
esac

echo "[run] Starting powerpanel-gateway on :${POWERPANEL_GATEWAY_PORT}"
exec python -m uvicorn powerpanel_gateway.main:app \
    --host "0.0.0.0" \
    --port "${POWERPANEL_GATEWAY_PORT}" \
    --log-level "${LOG_LEVEL}"
