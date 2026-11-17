from datetime import timedelta

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
