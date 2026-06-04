#!/usr/bin/with-contenv bashio
# shellcheck shell=bash
# Entrypoint for the PowerPanel Gateway.
#
# Works in two situations:
#   1. As a Home Assistant add-on: /data/options.json exists, so options are read
#      via bashio and seeded into /data/config.json.
#   2. As a plain container (e.g. `docker run -e POWERPANEL_GATEWAY_MOCK=1 ...`):
#      no options.json, so we skip seeding and rely on POWERPANEL_GATEWAY_* env.
set -e

DATA_DIR="${POWERPANEL_GATEWAY_DATA_DIR:-/data}"
CONFIG_FILE="${DATA_DIR}/config.json"

export POWERPANEL_GATEWAY_DATA_DIR="${DATA_DIR}"
export POWERPANEL_GATEWAY_HOST="0.0.0.0"
export POWERPANEL_GATEWAY_PORT="8099"
mkdir -p "${DATA_DIR}"

if bashio::fs.file_exists '/data/options.json'; then
    # ---- Home Assistant add-on path -------------------------------------
    bashio::log.info "Add-on options detected; seeding config from options."

    export POWERPANEL_GATEWAY_MOCK="$(bashio::config 'mock_mode')"
    export POWERPANEL_GATEWAY_LOG_LEVEL="$(bashio::config 'log_level' | tr '[:lower:]' '[:upper:]')"
    export POWERPANEL_GATEWAY_PWRSTAT_PATH="$(bashio::config 'pwrstat_path')"
    export POWERPANEL_GATEWAY_START_PWRSTATD="$(bashio::config 'start_pwrstatd')"
    if bashio::config.has_value 'api_token'; then
        export POWERPANEL_GATEWAY_API_TOKEN="$(bashio::config 'api_token')"
    fi

    # Add-on options are authoritative on each start. Live edits made in the web
    # UI persist until the next restart, when options are re-applied.
    jq -n \
      --argjson poll "$(bashio::config 'poll_interval_seconds')" \
      --argjson low "$(bashio::config 'low_battery_percent')" \
      --argjson crit "$(bashio::config 'critical_battery_percent')" \
      --arg ha_url "$(bashio::config 'home_assistant_url')" \
      --argjson email_enabled "$(bashio::config 'email.enabled')" \
      --arg smtp_host "$(bashio::config 'email.smtp_host')" \
      --argjson smtp_port "$(bashio::config 'email.smtp_port')" \
      --arg smtp_username "$(bashio::config 'email.smtp_username')" \
      --arg smtp_password "$(bashio::config 'email.smtp_password')" \
      --argjson smtp_use_tls "$(bashio::config 'email.smtp_use_tls')" \
      --arg smtp_from "$(bashio::config 'email.smtp_from')" \
      --arg smtp_to "$(bashio::config 'email.smtp_to')" \
      --argjson cooldown "$(bashio::config 'email.cooldown_minutes')" \
      --argjson e_pf "$(bashio::config 'email.send_power_failure')" \
      --argjson e_pr "$(bashio::config 'email.send_power_restored')" \
      --argjson e_lb "$(bashio::config 'email.send_low_battery')" \
      --argjson e_sp "$(bashio::config 'email.send_shutdown_pending')" \
      --argjson e_cl "$(bashio::config 'email.send_comm_lost')" \
      --argjson e_ds "$(bashio::config 'email.send_daily_summary')" \
      --argjson sd_enabled "$(bashio::config 'shutdown.enabled')" \
      --argjson sd_dry "$(bashio::config 'shutdown.dry_run')" \
      --argjson sd_after "$(bashio::config 'shutdown.shutdown_after_minutes_on_battery')" \
      --argjson sd_batt "$(bashio::config 'shutdown.shutdown_below_battery_percent')" \
      --argjson sd_rt "$(bashio::config 'shutdown.shutdown_below_runtime_minutes')" \
      --arg sd_cmd "$(bashio::config 'shutdown.shutdown_command')" \
      '{
        poll_interval_seconds: $poll,
        low_battery_percent: $low,
        critical_battery_percent: $crit,
        home_assistant_url: $ha_url,
        email: {
          enabled: $email_enabled,
          smtp_host: $smtp_host,
          smtp_port: $smtp_port,
          smtp_username: $smtp_username,
          smtp_password: $smtp_password,
          smtp_use_tls: $smtp_use_tls,
          smtp_from: $smtp_from,
          smtp_to: $smtp_to,
          cooldown_minutes: $cooldown,
          send_power_failure: $e_pf,
          send_power_restored: $e_pr,
          send_low_battery: $e_lb,
          send_shutdown_pending: $e_sp,
          send_comm_lost: $e_cl,
          send_daily_summary: $e_ds
        },
        shutdown: {
          enabled: $sd_enabled,
          dry_run: $sd_dry,
          shutdown_after_minutes_on_battery: $sd_after,
          shutdown_below_battery_percent: $sd_batt,
          shutdown_below_runtime_minutes: $sd_rt,
          shutdown_command: $sd_cmd
        }
      }' > "${CONFIG_FILE}"
    # Never echo the rendered config: it contains the SMTP password.
else
    # ---- Plain container path -------------------------------------------
    bashio::log.info "No /data/options.json; using POWERPANEL_GATEWAY_* env vars."
fi

# uvicorn only understands a fixed set of log levels; map HA-style names onto it.
case "$(echo "${POWERPANEL_GATEWAY_LOG_LEVEL:-info}" | tr '[:upper:]' '[:lower:]')" in
    trace) UVICORN_LOG_LEVEL="trace" ;;
    debug) UVICORN_LOG_LEVEL="debug" ;;
    warning|notice) UVICORN_LOG_LEVEL="warning" ;;
    error) UVICORN_LOG_LEVEL="error" ;;
    fatal|critical) UVICORN_LOG_LEVEL="critical" ;;
    *) UVICORN_LOG_LEVEL="info" ;;
esac

if [ "${POWERPANEL_GATEWAY_MOCK}" = "true" ] || [ "${POWERPANEL_GATEWAY_MOCK}" = "1" ]; then
    bashio::log.warning "Starting in MOCK mode (no real UPS required)."
else
    PWRSTAT_BIN="${POWERPANEL_GATEWAY_PWRSTAT_PATH:-pwrstat}"
    if command -v "${PWRSTAT_BIN}" >/dev/null 2>&1; then
        # `pwrstat` is only a client; the `pwrstatd` daemon must run alongside it
        # and is what actually owns the USB connection to the UPS.
        if command -v pwrstatd >/dev/null 2>&1 \
           && [ "${POWERPANEL_GATEWAY_START_PWRSTATD:-true}" = "true" ]; then
            bashio::log.info "Starting pwrstatd daemon..."
            pwrstatd || bashio::log.warning "pwrstatd failed to start; check USB access."
            sleep 2
        fi
    else
        bashio::log.warning "pwrstat not found at '${PWRSTAT_BIN}'."
        bashio::log.warning "Gateway will report 'communication_lost' until PowerPanel is installed."
        bashio::log.warning "To enable real mode: drop your CyberPower PowerPanel .deb into the"
        bashio::log.warning "add-on's vendor/ folder and rebuild. See DOCS.md -> 'Real UPS mode'."
    fi
fi

bashio::log.info "Starting PowerPanel Gateway on :8099 (Ingress)."
exec python -m uvicorn powerpanel_gateway.main:app \
    --host "0.0.0.0" \
    --port "8099" \
    --log-level "${UVICORN_LOG_LEVEL}"
