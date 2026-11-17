import json
from datetime import timedelta

import httpx

import influx as influx_module
from database import SessionLocal
from models import Game, GameSession, utcnow


def heartbeat_payload(games=None):
    return {
        "agent_id": "pc-test",
        "hostname": "DESKTOP-TEST",
        "games": games if games is not None else [],
    }


def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["steam_configured"] is False
    assert body["setup_required"] is False
    assert client.get("/docs").status_code == 200
    assert client.get("/redoc").status_code == 200


def test_setup_login_logout(anon_client, admin_credentials):
    status = anon_client.get("/api/auth/status").json()
    assert status["needs_setup"] is True
    assert status["authenticated"] is False
    assert anon_client.get("/api/stats/summary").status_code == 401
    assert anon_client.get("/docs").status_code == 401

    setup = anon_client.post("/api/auth/setup", json=admin_credentials)
    assert setup.status_code == 200, setup.text
    assert setup.json()["role"] == "admin"
    assert anon_client.get("/api/stats/summary").status_code == 200

    second_setup = anon_client.post("/api/auth/setup", json=admin_credentials)
    assert second_setup.status_code == 409

    assert anon_client.post("/api/auth/logout").status_code == 200
    assert anon_client.get("/api/auth/status").json()["authenticated"] is False
    assert anon_client.get("/api/stats/summary").status_code == 401

    bad_login = anon_client.post(
        "/api/auth/login",
        json={"identifier": "admin", "password": "wrong-password"},
    )
    assert bad_login.status_code == 401

    login = anon_client.post(
        "/api/auth/login",
        json={"identifier": "admin", "password": admin_credentials["password"]},
    )
    assert login.status_code == 200
    assert anon_client.get("/api/auth/me").json()["username"] == "admin"


def test_heartbeat_requires_key(client):
    response = client.post("/api/heartbeat", json=heartbeat_payload())
    assert response.status_code == 401


def test_heartbeat_creates_and_closes_session(client, agent_headers):
    first = client.post(
        "/api/heartbeat",
        json=heartbeat_payload(
            [{"name": "Elden Ring", "steam_app_id": 1245620, "process": "eldenring.exe"}]
        ),
        headers=agent_headers,
    )
    assert first.status_code == 200, first.text
    assert len(first.json()["active_sessions"]) == 1
    assert first.json()["active_sessions"][0]["game_name"] == "Elden Ring"

    second = client.post(
        "/api/heartbeat",
        json=heartbeat_payload([]),
        headers=agent_headers,
    )
    assert second.status_code == 200
    assert second.json()["active_sessions"] == []

    sessions = client.get("/api/sessions").json()
    assert len(sessions) == 1
    assert sessions[0]["game_name"] == "Elden Ring"
    assert sessions[0]["is_live"] is False
    assert sessions[0]["source"] == "agent"

    summary = client.get("/api/stats/summary").json()
    assert summary["active_count"] == 0
    assert summary["library_count"] == 1
    assert summary["agents_total"] == 1
    assert summary["agents_online"] == 1


def test_steam_game_is_reused_by_app_id(client, agent_headers):
    with SessionLocal() as db:
        db.add(
            Game(
                name="Elden Ring",
                name_key="elden ring",
                steam_app_id=1245620,
                steam_playtime_minutes=120,
            )
        )
        db.commit()

    response = client.post(
        "/api/heartbeat",
        json=heartbeat_payload(
            [{"name": "ELDEN RING", "steam_app_id": 1245620, "process": "eldenring.exe"}]
        ),
        headers=agent_headers,
    )
    assert response.status_code == 200

    games = client.get("/api/games").json()
    assert len(games) == 1
    assert games[0]["steam_playtime_minutes"] == 120


def test_stats_aggregate_closed_session(client):
    now = utcnow()
    with SessionLocal() as db:
        game = Game(name="Hades", name_key="hades", steam_app_id=1145360)
        db.add(game)
        db.flush()
        db.add(
            GameSession(
                game_id=game.id,
                source="agent",
                started_at=now - timedelta(hours=3),
                ended_at=now - timedelta(hours=1),
                last_heartbeat_at=now - timedelta(hours=1),
                duration_seconds=7200,
            )
        )
        db.commit()

    summary = client.get("/api/stats/summary").json()
    assert summary["total_seconds"] >= 7200

    top = client.get("/api/stats/top-games?days=30").json()
    assert top[0]["name"] == "Hades"
    assert top[0]["tracked_seconds"] >= 7200

    heatmap = client.get("/api/stats/heatmap?days=365").json()
    assert heatmap["max_seconds"] >= 3600
    assert len(heatmap["cells"]) == 7 * 24

    daily = client.get("/api/stats/daily?days=14").json()
    assert daily["days"] == 14
    assert len(daily["items"]) == 14
    assert daily["max_seconds"] >= 3600

    sessions = client.get("/api/sessions").json()
    assert sessions[0]["duration_seconds"] == 7200


def test_user_management(client):
    created = client.post(
        "/api/users",
        json={
            "username": "viewer",
            "email": "viewer@example.com",
            "password": "viewer-password",
            "role": "viewer",
        },
    )
    assert created.status_code == 201, created.text
    viewer_id = created.json()["id"]

    users = client.get("/api/users").json()
    assert {user["username"] for user in users} == {"admin", "viewer"}

    updated = client.patch(
        f"/api/users/{viewer_id}",
        json={"role": "admin", "is_active": False},
    )
    assert updated.status_code == 200
    assert updated.json()["role"] == "admin"
    assert updated.json()["is_active"] is False

    self_delete = client.delete("/api/users/1")
    assert self_delete.status_code == 400

    deleted = client.delete(f"/api/users/{viewer_id}")
    assert deleted.status_code == 204


def test_settings_and_agent_key_rotation(client, agent_headers):
    current = client.get("/api/settings")
    assert current.status_code == 200
    assert current.json()["agent_api_key_set"] is True

    updated = client.patch(
        "/api/settings",
        json={"steam_id": "76561198000000000", "timezone": "Europe/London"},
    )
    assert updated.status_code == 200
    assert updated.json()["steam_id"] == "76561198000000000"
    assert updated.json()["timezone"] == "Europe/London"

    rotated = client.post("/api/settings/agent-key/rotate")
    assert rotated.status_code == 200
    new_key = rotated.json()["agent_api_key"]

    rejected = client.post(
        "/api/heartbeat",
        json=heartbeat_payload(),
        headers=agent_headers,
    )
    assert rejected.status_code == 401

    accepted = client.post(
        "/api/heartbeat",
        json=heartbeat_payload(),
        headers={"X-Agent-Key": new_key},
    )
    assert accepted.status_code == 200


def test_homepage_api_and_token_rotation(client):
    missing = client.get("/api/homepage?token=anything")
    assert missing.status_code == 503

    updated = client.patch(
        "/api/settings",
        json={"homepage_api_token": "homepage-secret-token"},
    )
    assert updated.status_code == 200
    assert updated.json()["homepage_api_token_set"] is True

    response = client.get("/api/homepage?token=homepage-secret-token")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "today_seconds" in data
    assert "active_games" in data

    header_response = client.get(
        "/api/homepage",
        headers={"X-API-Key": "homepage-secret-token"},
    )
    assert header_response.status_code == 200
    assert client.get("/api/homepage?token=wrong").status_code == 401

    rotated = client.post("/api/settings/homepage-token/rotate")
    assert rotated.status_code == 200
    new_token = rotated.json()["homepage_api_token"]
    assert new_token != "homepage-secret-token"
    assert (
        client.get("/api/homepage", headers={"X-API-Key": new_token}).status_code
        == 200
    )
    assert (
        client.get("/api/homepage", headers={"X-API-Key": "homepage-secret-token"}).status_code
        == 401
    )


def test_influx_export(client, monkeypatch):
    configured = client.patch(
        "/api/settings",
        json={
            "influxdb_url": "http://influxdb:8086",
            "influxdb_token": "influx-token",
            "influxdb_org": "gamestats",
            "influxdb_bucket": "gaming",
            "influxdb_enabled": True,
        },
    )
    assert configured.status_code == 200, configured.text
    assert configured.json()["influxdb_configured"] is True

    now = utcnow()
    with SessionLocal() as db:
        game = Game(name="Hades", name_key="hades")
        db.add(game)
        db.flush()
        db.add(
            GameSession(
                game_id=game.id,
                source="agent",
                started_at=now - timedelta(hours=2),
                ended_at=now - timedelta(hours=1),
                last_heartbeat_at=now - timedelta(hours=1),
                duration_seconds=3600,
            )
        )
        db.commit()

    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.content.decode("utf-8")
        captured["url"] = str(request.url)
        return httpx.Response(204)

    real_client = httpx.Client(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(influx_module.httpx, "Client", lambda **_: real_client)
    try:
        result = client.post("/api/admin/influxdb/export")
    finally:
        real_client.close()

    assert result.status_code == 200, result.text
    payload = result.json()
    assert payload["skipped"] is False
    assert payload["sessions_exported"] == 1
    assert payload["points_written"] >= 2
    assert "gamestats_session" in captured["body"]
    assert "gamestats_summary" in captured["body"]
    assert "game=Hades" in captured["body"]
    assert "/api/v2/write" in captured["url"]


def test_update_locale(client):
    updated = client.patch("/api/auth/me", json={"locale": "en"})
    assert updated.status_code == 200
    assert updated.json()["locale"] == "en"
    assert client.get("/api/auth/me").json()["locale"] == "en"


def test_backup_json_roundtrip(client, admin_credentials):
    exported = client.get("/api/admin/backup/export/json")
    assert exported.status_code == 200
    payload = exported.json()
    assert payload["format"] == "gamestats-backup"
    assert payload["version"] == 1
    assert "users" in payload["tables"]
    assert "games" in payload["tables"]
    assert "auth_sessions" not in payload["tables"]

    restored = client.post(
        "/api/admin/backup/import/json",
        files={
            "file": (
                "backup.json",
                json.dumps(payload).encode("utf-8"),
                "application/json",
            )
        },
    )
    assert restored.status_code == 200, restored.text

    status = client.get("/api/auth/status").json()
    assert status["authenticated"] is False
    assert status["needs_setup"] is False

    login = client.post(
        "/api/auth/login",
        json={"identifier": "admin", "password": admin_credentials["password"]},
    )
    assert login.status_code == 200


def test_backup_sqlite_roundtrip(client, admin_credentials):
    exported = client.get("/api/admin/backup/export/sqlite")
    assert exported.status_code == 200
    assert exported.content.startswith(b"SQLite format 3\x00")

    restored = client.post(
        "/api/admin/backup/restore/sqlite",
        files={
            "file": (
                "backup.db",
                exported.content,
                "application/vnd.sqlite3",
            )
        },
    )
    assert restored.status_code == 200, restored.text
    assert client.get("/api/auth/status").json()["authenticated"] is False

    login = client.post(
        "/api/auth/login",
        json={"identifier": "admin", "password": admin_credentials["password"]},
    )
    assert login.status_code == 200


def test_viewer_cannot_access_settings_or_users(anon_client, admin_credentials):
    anon_client.post("/api/auth/setup", json=admin_credentials)
    anon_client.post(
        "/api/users",
        json={
            "username": "reader",
            "password": "reader-password",
            "role": "viewer",
        },
    )
    anon_client.post("/api/auth/logout")
    anon_client.post(
        "/api/auth/login",
        json={"identifier": "reader", "password": "reader-password"},
    )

    assert anon_client.get("/api/settings").status_code == 403
    assert anon_client.get("/api/users").status_code == 403
    assert anon_client.get("/api/stats/summary").status_code == 200
