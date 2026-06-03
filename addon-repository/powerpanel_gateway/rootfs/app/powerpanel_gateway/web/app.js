// PowerPanel Gateway UI — dependency-free, Ingress-safe.
// All requests use relative URLs so the Home Assistant Ingress path prefix works.
"use strict";

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

// Resolve API base relative to the current document (handles Ingress prefix).
const BASE = new URL(".", window.location.href).href;
const api = (path) => new URL(path.replace(/^\//, ""), BASE).href;

async function getJSON(path) {
  const res = await fetch(api(path), { headers: { Accept: "application/json" } });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}
async function postJSON(path, body) {
  const res = await fetch(api(path), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `${res.status}`);
  return data;
}

const fmt = (v, unit = "") => (v === null || v === undefined ? "–" : `${v}${unit}`);

// -- tab switching ----------------------------------------------------------
$$(".tab").forEach((tab) =>
  tab.addEventListener("click", () => {
    $$(".tab").forEach((t) => t.classList.remove("active"));
    $$(".panel").forEach((p) => p.classList.remove("active"));
    tab.classList.add("active");
    $(`#panel-${tab.dataset.tab}`).classList.add("active");
    if (tab.dataset.tab === "events") loadEvents();
    if (tab.dataset.tab === "diagnostics") loadDiagnostics();
    if (tab.dataset.tab === "shutdown") loadShutdownPreview();
  })
);

// -- live status ------------------------------------------------------------
function renderStatus(s) {
  const badge = $("#state-badge");
  badge.textContent = (s.state || "unknown").replace(/_/g, " ").toUpperCase();
  badge.className = `state-badge state-${s.state || "unknown"}`;
  $("#m-battery").textContent = fmt(s.battery_percent, " %");
  $("#m-runtime").textContent = fmt(s.remaining_runtime_minutes, " min");
  $("#m-load").textContent =
    s.load_percent != null ? `${s.load_percent} % (${fmt(s.load_watts)} W)` : "–";
  $("#m-utility").textContent = fmt(s.utility_voltage, " V");
  $("#m-output").textContent = fmt(s.output_voltage, " V");
  $("#m-model").textContent = s.model || "–";
  $("#updated-at").textContent = s.raw_updated_at
    ? `updated ${new Date(s.raw_updated_at).toLocaleTimeString()}`
    : "";
}

$("#btn-refresh").addEventListener("click", async () => {
  renderStatus(await postJSON("api/actions/refresh"));
});
$("#btn-selftest").addEventListener("click", async () => {
  const r = await postJSON("api/actions/self-test");
  alert(r.message);
});
$("#btn-mute").addEventListener("click", async () => {
  const r = await postJSON("api/actions/mute-alarm");
  alert(r.message);
});

// -- events -----------------------------------------------------------------
let lastEvents = [];
async function loadEvents() {
  const type = $("#event-filter").value;
  lastEvents = await getJSON("api/events?limit=500" + (type ? `&type=${type}` : ""));
  const body = $("#events-body");
  body.innerHTML = "";
  for (const e of lastEvents) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${new Date(e.timestamp).toLocaleString()}</td>
      <td>${e.type}</td><td>${e.message || ""}</td>
      <td>${e.battery_percent != null ? e.battery_percent + " %" : ""}</td>`;
    body.appendChild(tr);
  }
}
$("#event-filter").addEventListener("change", loadEvents);
$("#btn-export-events").addEventListener("click", () => {
  download("events.json", JSON.stringify(lastEvents, null, 2));
});

function populateEventTypes() {
  const types = [
    "power_failure_started", "power_restored", "battery_low", "battery_critical",
    "shutdown_countdown_started", "shutdown_cancelled", "self_test_started",
    "self_test_passed", "self_test_failed", "communication_lost",
    "communication_restored", "email_sent", "email_failed",
  ];
  const sel = $("#event-filter");
  for (const t of types) {
    const opt = document.createElement("option");
    opt.value = t;
    opt.textContent = t;
    sel.appendChild(opt);
  }
}

// -- email ------------------------------------------------------------------
async function loadEmail() {
  const cfg = (await getJSON("api/config")).email;
  const f = $("#email-form");
  for (const [k, v] of Object.entries(cfg)) {
    const el = f.elements[k];
    if (!el) continue;
    if (el.type === "checkbox") el.checked = !!v;
    else if (k === "smtp_to") el.value = (v || []).join(", ");
    else if (k !== "smtp_password_set") el.value = v;
  }
}
$("#email-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const f = ev.target;
  const email = {
    enabled: f.enabled.checked,
    smtp_host: f.smtp_host.value,
    smtp_port: Number(f.smtp_port.value),
    smtp_username: f.smtp_username.value,
    smtp_use_tls: f.smtp_use_tls.checked,
    smtp_from: f.smtp_from.value,
    smtp_to: f.smtp_to.value,
    cooldown_minutes: Number(f.cooldown_minutes.value),
    send_power_failure: f.send_power_failure.checked,
    send_power_restored: f.send_power_restored.checked,
    send_low_battery: f.send_low_battery.checked,
    send_shutdown_pending: f.send_shutdown_pending.checked,
    send_comm_lost: f.send_comm_lost.checked,
    send_daily_summary: f.send_daily_summary.checked,
  };
  // Only send the password if the user typed one (avoid clobbering).
  if (f.smtp_password.value) email.smtp_password = f.smtp_password.value;
  await postJSON("api/config", { email });
  f.smtp_password.value = "";
  $("#email-status").textContent = "Saved.";
});
$("#btn-test-email").addEventListener("click", async () => {
  $("#email-status").textContent = "Sending…";
  try {
    const r = await postJSON("api/actions/test-email");
    $("#email-status").textContent = r.message;
  } catch (e) {
    $("#email-status").textContent = "Error: " + e.message;
  }
});

// -- shutdown ---------------------------------------------------------------
async function loadShutdown() {
  const cfg = (await getJSON("api/config")).shutdown;
  const f = $("#shutdown-form");
  for (const [k, v] of Object.entries(cfg)) {
    const el = f.elements[k];
    if (!el) continue;
    if (el.type === "checkbox") el.checked = !!v;
    else el.value = v;
  }
}
async function loadShutdownPreview() {
  await loadShutdown();
  const ev = await getJSON("api/shutdown/evaluate");
  $("#shutdown-preview").textContent = JSON.stringify(ev, null, 2);
}
$("#shutdown-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const f = ev.target;
  const shutdown = {
    enabled: f.enabled.checked,
    dry_run: f.dry_run.checked,
    shutdown_after_minutes_on_battery: Number(f.shutdown_after_minutes_on_battery.value),
    shutdown_below_battery_percent: Number(f.shutdown_below_battery_percent.value),
    shutdown_below_runtime_minutes: Number(f.shutdown_below_runtime_minutes.value),
    shutdown_command: f.shutdown_command.value,
  };
  await postJSON("api/config", { shutdown });
  loadShutdownPreview();
});

// -- diagnostics ------------------------------------------------------------
async function loadDiagnostics() {
  const d = await getJSON("api/diagnostics");
  $("#diag-meta").textContent = JSON.stringify(
    {
      gateway_version: d.gateway_version,
      mock_mode: d.mock_mode,
      pwrstat_available: d.pwrstat_available,
      pwrstat_path: d.pwrstat_path,
      device_info: d.device_info,
      platform: d.platform,
    },
    null,
    2
  );
  $("#diag-raw").textContent = d.raw || "(none)";
  $("#diag-parsed").textContent = JSON.stringify(d.parsed, null, 2);
}
$("#btn-refresh-diag").addEventListener("click", loadDiagnostics);
$("#btn-download-diag").addEventListener("click", async () => {
  const d = await getJSON("api/diagnostics");
  download("diagnostics.json", JSON.stringify(d, null, 2));
});

// -- simulator --------------------------------------------------------------
$$(".sim").forEach((btn) =>
  btn.addEventListener("click", async () => {
    try {
      const r = await postJSON("api/actions/simulate", { scenario: btn.dataset.scenario });
      $("#sim-status").textContent = r.message;
    } catch (e) {
      $("#sim-status").textContent = "Error: " + e.message;
    }
  })
);

// -- helpers ----------------------------------------------------------------
function download(name, content) {
  const blob = new Blob([content], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = name;
  a.click();
  URL.revokeObjectURL(a.href);
}

// -- live event stream (SSE) ------------------------------------------------
function connectStream() {
  const src = new EventSource(api("api/stream"));
  src.onmessage = (msg) => {
    setConn(true);
    try {
      const payload = JSON.parse(msg.data);
      if (payload.type === "status") renderStatus(payload.data);
      else if (payload.type === "event" && $("#panel-events").classList.contains("active"))
        loadEvents();
    } catch (_) {}
  };
  src.onerror = () => {
    setConn(false);
    src.close();
    setTimeout(connectStream, 4000); // reconnect
  };
}
function setConn(ok) {
  const el = $("#conn-indicator");
  el.className = "pill " + (ok ? "pill-ok" : "pill-bad");
  el.textContent = ok ? "● live" : "● offline";
}

// -- bootstrap --------------------------------------------------------------
async function init() {
  populateEventTypes();
  try {
    const health = await getJSON("health");
    $("#version").textContent = "v" + health.version;
    if (health.mock_mode) $("#tab-simulator").hidden = false;
  } catch (_) {}
  try {
    renderStatus(await getJSON("api/status"));
  } catch (_) {}
  await loadEmail().catch(() => {});
  connectStream();
}
init();
