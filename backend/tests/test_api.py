import json
from datetime import timedelta

import httpx

import influx as influx_module
from collectors import epic as epic_module
from collectors import gog as gog_module
from collectors import ubisoft as ubisoft_module
from collectors import xbox as xbox_module
from collectors.ubisoft import parse_games_played
from collectors.xbox import parse_titles
from database import SessionLocal
from models import Game, GameSession, utcnow
from settings_service import (
    SETTING_EPIC_ACCOUNT_ID,
    SETTING_EPIC_REFRESH_TOKEN,
    SETTING_GOG_REFRESH_TOKEN,
    SETTING_GOG_USER_ID,
    SETTING_UBISOFT_REMEMBER_ME_TICKET,
    SETTING_XBOX_CLIENT_ID,
    SETTING_XBOX_REFRESH_TOKEN,
    update_settings,
)


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

def test_xbox_parse_title_history():
    titles = parse_titles(
        {
            "titles": [
                {
                    "titleId": "1234",
                    "name": "Halo Infinite",
                    "type": "Game",
                    "achievement": {
                        "currentAchievements": 4,
                        "totalAchievements": 10,
                        "currentGamerscore": 80,
                        "totalGamerscore": 200,
                    },
                    "titleHistory": {"lastTimePlayed": "2026-11-16T21:15:00.000Z"},
                    "displayImage": "https://images.example/halo.jpg",
                },
                {"titleId": "999", "name": "DLC", "type": "Dlc"},
            ]
        }
    )
    assert len(titles) == 1
    assert titles[0]["title_id"] == "1234"
    assert titles[0]["achievements_total"] == 10
    assert titles[0]["achievements_unlocked"] == 4
    assert titles[0]["gamerscore"] == 80
    assert titles[0]["last_played_at"] is not None


def test_xbox_endpoints_without_connection(client):
    start = client.post("/api/xbox/device-code")
    assert start.status_code == 400

    sync = client.post("/api/xbox/sync")
    assert sync.status_code == 200
    assert sync.json()["skipped"] is True


def test_xbox_sync_maps_titles_to_library(client, monkeypatch):
    with SessionLocal() as db:
        update_settings(
            db,
            {
                SETTING_XBOX_CLIENT_ID: "azure-client-id",
                SETTING_XBOX_REFRESH_TOKEN: "refresh-token",
            },
        )

    monkeypatch.setattr(
        xbox_module,
        "refresh_microsoft_token",
        lambda *_: {"access_token": "ms-access", "refresh_token": "new-refresh"},
    )
    monkeypatch.setattr(
        xbox_module,
        "authenticate_xbox",
        lambda *_: {"xuid": "123", "userhash": "uhs", "token": "xsts"},
    )
    monkeypatch.setattr(
        xbox_module,
        "fetch_profile",
        lambda *_: {"gamertag": "Player One", "gamerscore": 1234},
    )
    monkeypatch.setattr(
        xbox_module,
        "fetch_title_history",
        lambda *_: {
            "titles": [
                {
                    "titleId": "1234",
                    "name": "Halo Infinite",
                    "type": "Game",
                    "achievement": {
                        "currentAchievements": 4,
                        "totalAchievements": 10,
                        "currentGamerscore": 80,
                        "totalGamerscore": 200,
                    },
                    "titleHistory": {"lastTimePlayed": "2026-11-16T21:15:00.000Z"},
                    "displayImage": "https://images.example/halo.jpg",
                }
            ]
        },
    )

    with SessionLocal() as db:
        result = xbox_module.sync_xbox_library(db)

    assert result["skipped"] is False
    assert result["titles_synced"] == 1
    assert result["gamerscore"] == 1234

    games = client.get("/api/games").json()
    assert len(games) == 1
    game = games[0]
    assert game["name"] == "Halo Infinite"
    assert game["xbox_title_id"] == "1234"
    assert game["xbox_achievements_unlocked"] == 4
    assert game["xbox_achievements_total"] == 10
    assert game["xbox_gamerscore"] == 80
    assert game["xbox_gamerscore_total"] == 200

    settings = client.get("/api/settings").json()
    assert settings["xbox_connected"] is True
    assert settings["xbox_gamertag"] == "Player One"
    assert settings["xbox_gamerscore"] == 1234

def test_ubisoft_parse_games_played():
    entries = parse_games_played(
        {
            "gamesPlayed": [
                {
                    "spaceId": "abc-space",
                    "spacePlatformType": "uplay",
                    "firstPlayed": {"createdAt": "2025-01-01T10:00:00Z"},
                    "lastPlayed": {"updatedAt": "2026-11-16T21:15:00Z"},
                    "sessionsCount": 12,
                    "applications": [
                        {
                            "applicationId": "app-1",
                            "sessionsCount": 12,
                        }
                    ],
                }
            ]
        }
    )
    assert len(entries) == 1
    assert entries[0]["space_id"] == "abc-space"
    assert entries[0]["sessions_count"] == 12
    assert entries[0]["first_played_at"] is not None
    assert entries[0]["last_played_at"] is not None


def test_ubisoft_endpoints_without_connection(client):
    sync = client.post("/api/ubisoft/sync")
    assert sync.status_code == 200
    assert sync.json()["connected"] is False

    disconnect = client.post("/api/ubisoft/disconnect")
    assert disconnect.status_code == 200


def test_ubisoft_sync_maps_library(client, monkeypatch):
    with SessionLocal() as db:
        update_settings(
            db, {SETTING_UBISOFT_REMEMBER_ME_TICKET: "remember-me-ticket"}
        )

    class FakeUbisoftClient:
        def __init__(self, _ticket):
            self.ticket = _ticket

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def login(self):
            return {
                "ticket": "session-ticket",
                "rememberMeTicket": "new-remember-ticket",
                "profileId": "profile-1",
                "userId": "user-1",
                "nameOnPlatform": "Ubisoft Player",
            }

        def games_played(self, _session):
            return [
                {
                    "space_id": "space-1",
                    "sessions_count": 7,
                    "first_played_at": utcnow() - timedelta(days=30),
                    "last_played_at": utcnow() - timedelta(days=1),
                    "application_ids": ["app-1"],
                }
            ]

        def space_name(self, _space_id, _session):
            return "Assassin's Creed Mirage"

    monkeypatch.setattr(ubisoft_module, "UbisoftClient", FakeUbisoftClient)

    with SessionLocal() as db:
        result = ubisoft_module.sync_ubisoft_library(db)

    assert result["connected"] is True
    assert result["games_synced"] == 1
    assert result["name"] == "Ubisoft Player"

    games = client.get("/api/games").json()
    assert len(games) == 1
    game = games[0]
    assert game["name"] == "Assassin's Creed Mirage"
    assert game["ubisoft_space_id"] == "space-1"
    assert game["ubisoft_sessions_count"] == 7
    assert game["ubisoft_last_played_at"] is not None

    settings = client.get("/api/settings").json()
    assert settings["ubisoft_connected"] is True
    assert settings["ubisoft_name"] == "Ubisoft Player"
def test_gog_extract_code():
    from routes_gog import _extract_code

    assert _extract_code("abc123def456") == "abc123def456"
    assert (
        _extract_code(
            "https://embed.gog.com/on_login_success?origin=client&code=token-code-1"
        )
        == "token-code-1"
    )


def test_gog_auth_url(client):
    response = client.get("/api/gog/auth-url")
    assert response.status_code == 200
    body = response.json()
    assert "auth.gog.com/auth" in body["url"]
    assert "client_id=46899977096215655" in body["url"]
    assert "response_type=code" in body["url"]
    assert "embed.gog.com" in body["redirect_uri"]


def test_gog_endpoints_without_connection(client):
    sync = client.post("/api/gog/sync")
    assert sync.status_code == 200
    assert sync.json()["connected"] is False

    settings = client.get("/api/settings").json()
    assert settings["gog_connected"] is False
    assert settings["gog_refresh_token_set"] is False

    disconnect = client.post("/api/gog/disconnect")
    assert disconnect.status_code == 200


def test_gog_sync_maps_library(client, monkeypatch):
    with SessionLocal() as db:
        update_settings(
            db,
            {
                SETTING_GOG_REFRESH_TOKEN: "refresh-token",
                SETTING_GOG_USER_ID: "12345",
            },
        )

    class FakeGogClient:
        def __init__(self, _refresh_token=""):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def refresh(self):
            return {
                "access_token": "access-token",
                "refresh_token": "new-refresh-token",
                "user_id": "12345",
            }

        def user_data(self, _access_token):
            return {"username": "Gog Player", "userId": "12345"}

        def owned_product_ids(self, _access_token):
            return [1207658691, 999]

        def products(self, _product_ids):
            return [
                {
                    "id": 1207658691,
                    "title": "The Witcher 3: Wild Hunt",
                    "game_type": "game",
                    "images": {"background": "//images.gog.com/witcher3.jpg"},
                },
                {
                    "id": 999,
                    "title": "Bonus Soundtrack",
                    "game_type": "dlc",
                },
            ]

        def achievements(self, _product_id, _user_id, _access_token):
            return 52, 17

    monkeypatch.setattr(gog_module, "GogClient", FakeGogClient)

    response = client.post("/api/gog/sync")
    assert response.status_code == 200
    body = response.json()
    assert body["connected"] is True
    assert body["name"] == "Gog Player"
    assert body["games_synced"] == 1

    games = client.get("/api/games").json()
    assert len(games) == 1
    game = games[0]
    assert game["name"] == "The Witcher 3: Wild Hunt"
    assert game["gog_product_id"] == 1207658691
    assert game["gog_achievements_total"] == 52
    assert game["gog_achievements_unlocked"] == 17
    assert game["cover_url"] == "https://images.gog.com/witcher3.jpg"

    settings = client.get("/api/settings").json()
    assert settings["gog_connected"] is True
    assert settings["gog_username"] == "Gog Player"
    assert settings["gog_last_sync_at"] is not None
def test_epic_extract_code():
    from routes_epic import _extract_code

    assert _extract_code("abc123def456") == "abc123def456"
    assert (
        _extract_code(
            '{"warning":"x","authorizationCode":"auth-code-1","exchangeCode":null}'
        )
        == "auth-code-1"
    )
    assert (
        _extract_code(
            "https://www.epicgames.com/id/api/redirect?clientId=abc&code=url-code"
        )
        == "url-code"
    )


def test_epic_auth_url(client):
    response = client.get("/api/epic/auth-url")
    assert response.status_code == 200
    body = response.json()
    assert "epicgames.com/id/login" in body["url"]
    assert "clientId=34a02cf8f4414e29b15921876da36f9a" in body["redirect_uri"]


def test_epic_endpoints_without_connection(client):
    sync = client.post("/api/epic/sync")
    assert sync.status_code == 200
    assert sync.json()["connected"] is False

    settings = client.get("/api/settings").json()
    assert settings["epic_connected"] is False
    assert settings["epic_refresh_token_set"] is False

    disconnect = client.post("/api/epic/disconnect")
    assert disconnect.status_code == 200


def test_epic_sync_maps_library(client, monkeypatch):
    with SessionLocal() as db:
        update_settings(
            db,
            {
                SETTING_EPIC_REFRESH_TOKEN: "refresh-token",
                SETTING_EPIC_ACCOUNT_ID: "account-1",
            },
        )

    class FakeEpicClient:
        def __init__(self, _refresh_token=""):
            self.account_id = ""

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def refresh(self):
            return {
                "access_token": "access-token",
                "refresh_token": "new-refresh-token",
                "account_id": "account-1",
                "displayName": "Epic Player",
            }

        def library_items(self, _access_token):
            return [
                {
                    "namespace": "ns-aw2",
                    "catalogItemId": "catalog-aw2",
                    "appName": "AppAW2",
                    "sandboxName": "AllenWake2",
                    "sandboxType": "PUBLIC",
                    "recordType": "APPLICATION",
                },
                {
                    "namespace": "ns-aw2",
                    "catalogItemId": "catalog-dlc",
                    "appName": "AppAW2DLC",
                    "sandboxName": "AllenWake2",
                    "sandboxType": "PUBLIC",
                    "recordType": "SUBSCRIPTION",
                },
                {
                    "namespace": "ue",
                    "catalogItemId": "catalog-ue",
                    "appName": "MarketplacePlugin",
                    "sandboxType": "PUBLIC",
                    "recordType": "APPLICATION",
                },
            ]

        def catalog_item(self, namespace, catalog_item_id, _access_token):
            assert namespace == "ns-aw2"
            assert catalog_item_id == "catalog-aw2"
            return {
                "title": "Alan Wake 2",
                "keyImages": [
                    {
                        "type": "OfferImageTall",
                        "url": "https://cdn.epicgames.com/aw2.jpg",
                    }
                ],
            }

        def achievements(self, namespace, _access_token):
            assert namespace == "ns-aw2"
            return 30, 12

    monkeypatch.setattr(epic_module, "EpicClient", FakeEpicClient)

    response = client.post("/api/epic/sync")
    assert response.status_code == 200
    body = response.json()
    assert body["connected"] is True
    assert body["name"] == "Epic Player"
    assert body["games_synced"] == 1

    games = client.get("/api/games").json()
    assert len(games) == 1
    game = games[0]
    assert game["name"] == "Alan Wake 2"
    assert game["epic_catalog_item_id"] == "catalog-aw2"
    assert game["epic_achievements_total"] == 30
    assert game["epic_achievements_unlocked"] == 12
    assert game["cover_url"] == "https://cdn.epicgames.com/aw2.jpg"

    settings = client.get("/api/settings").json()
    assert settings["epic_connected"] is True
    assert settings["epic_display_name"] == "Epic Player"
    assert settings["epic_last_sync_at"] is not None
