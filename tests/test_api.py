"""Tests for the REST API using the mock provider."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from powerpanel_gateway.config import Settings
from powerpanel_gateway.main import create_app


def test_health(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["mock_mode"] is True


def test_status_initial(client: TestClient) -> None:
    body = client.get("/api/status").json()
    assert body["ok"] is True
    assert body["state"] == "normal"
    assert body["on_battery"] is False


def test_simulate_power_failure_then_restore(client: TestClient) -> None:
    resp = client.post("/api/actions/simulate", json={"scenario": "power_failure"})
    assert resp.status_code == 200
    status = client.get("/api/status").json()
    assert status["state"] == "on_battery"
    assert status["on_battery"] is True

    # An event should have been recorded.
    events = client.get("/api/events").json()
    assert any(e["type"] == "power_failure_started" for e in events)

    client.post("/api/actions/simulate", json={"scenario": "power_restored"})
    status = client.get("/api/status").json()
    assert status["on_battery"] is False
    events = client.get("/api/events").json()
    assert any(e["type"] == "power_restored" for e in events)


def test_simulate_rejects_unknown_scenario(client: TestClient) -> None:
    resp = client.post("/api/actions/simulate", json={"scenario": "explode"})
    assert resp.status_code == 422  # schema rejects the value


def test_config_get_has_no_password(client: TestClient) -> None:
    body = client.get("/api/config").json()
    assert "smtp_password" not in body["email"]
    assert "smtp_password_set" in body["email"]


def test_config_post_updates(client: TestClient) -> None:
    resp = client.post("/api/config", json={"poll_interval_seconds": 30})
    assert resp.status_code == 200
    assert resp.json()["poll_interval_seconds"] == 30


def test_config_post_rejects_invalid(client: TestClient) -> None:
    resp = client.post("/api/config", json={"poll_interval_seconds": 0})
    assert resp.status_code == 422


def test_config_post_rejects_non_object(client: TestClient) -> None:
    resp = client.post("/api/config", json=[1, 2, 3])
    assert resp.status_code == 400


def test_shutdown_evaluation_default_safe(client: TestClient) -> None:
    body = client.get("/api/shutdown/evaluate").json()
    assert body["dry_run"] is True
    assert body["enabled"] is False
    assert body["would_shutdown"] is False


def test_raw_endpoint(client: TestClient) -> None:
    body = client.get("/api/raw").json()
    assert body["source"] == "mock"
    assert "UPS" in body["raw"]


def test_diagnostics(client: TestClient) -> None:
    body = client.get("/api/diagnostics").json()
    assert body["mock_mode"] is True
    assert "status" in body
    assert "parsed" in body


def test_self_test_and_mute(client: TestClient) -> None:
    assert client.post("/api/actions/self-test").json()["ok"] is True
    assert client.post("/api/actions/mute-alarm").json()["ok"] is True


def test_auth_required_when_token_set(tmp_path: Path) -> None:
    app = create_app(Settings(mock=True, data_dir=tmp_path, api_token="s3cret"))
    with TestClient(app) as c:
        # health stays open
        assert c.get("/health").status_code == 200
        # api requires the token
        assert c.get("/api/status").status_code == 401
        ok = c.get("/api/status", headers={"Authorization": "Bearer s3cret"})
        assert ok.status_code == 200
        bad = c.get("/api/status", headers={"Authorization": "Bearer nope"})
        assert bad.status_code == 401
