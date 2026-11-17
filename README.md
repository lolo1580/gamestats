# GameStats

Self-hosted gaming activity dashboard for your PC and Steam library. A small
Windows agent reports the games currently running, while the backend keeps a
history of sessions, synchronizes Steam playtime and achievements, and fetches
covers and genres from IGDB.

The interface is currently in French and ships with **dark and light themes**.

## Features

- **Real-time sessions** — the Windows agent sends a heartbeat every 30 seconds;
  the backend opens, extends, and closes game sessions automatically.
- **Dashboard** — key metrics, a 14-day activity chart, a live session card, an
  annual heatmap, top games, and recent sessions.
- **Steam library sync** — owned games, total and two-week playtime, last played
  dates, and achievement progress. Playtime deltas become approximate sessions.
- **Double-count protection** — Steam playtime deltas already covered by an
  agent session are ignored.
- **IGDB enrichment** — HD covers and genres for games that do not have them yet.
- **Session history** — filter by source (PC agent or Steam), search by game,
  and group sessions by day.
- **Library** — search, sort, inspect playtime and achievement progress.
- **Light / dark theme** — switch from the header; the preference is stored in
  the browser and applied before the first render.
- **Docker Compose** — backend, SQLite persistence, and an nginx-served frontend.
- **Single shared secret** — write endpoints are protected by an agent API key.

## Architecture

```text
agent-windows/tracker.py ── POST /api/heartbeat ──► backend (FastAPI)
                                                        │
                                    ┌───────────────────┼────────────────────┐
                                    ▼                   ▼                    ▼
                              SQLite database      APScheduler          Steam Web API
                              /data/*.db           every minute         + IGDB API
                                                        │
frontend (React/nginx) ◄──────── GET /api/* ────────────┘
```

- **Agent** scans local processes with `psutil`. No screenshots, file contents,
  or game data are collected.
- **Backend** stores games, sessions, playtime snapshots, achievements, and agent
  state. Agent sessions are closed after `AGENT_STALE_SECONDS` without a
  heartbeat.
- **Scheduler** closes stale sessions every minute, syncs Steam every 15 minutes,
  and enriches IGDB data every 60 minutes. Run a single uvicorn worker so the
  scheduler is not duplicated.
- **Frontend** is a React/Vite SPA served by nginx. `/api` is proxied to the
  backend.

## Quick start

Requirements: Docker Engine with Docker Compose v2.

```bash
git clone https://github.com/lolo1580/gamestats.git
cd gamestats
cp .env.example .env
# Edit .env and at least set AGENT_API_KEY
docker compose up -d --build
```

| Service     | URL                                  |
| ----------- | ------------------------------------ |
| Dashboard   | http://localhost:8090                |
| API / docs  | http://localhost:8091/docs           |
| Healthcheck | http://localhost:8091/api/health     |

The host ports are configurable through `FRONTEND_PORT` and `BACKEND_PORT`
(defaults: `8090` and `8091`, chosen to avoid the frequently used `8080`/`8000`).
The backend port must be reachable from the Windows PC running the agent.

SQLite data is stored in `./data/gamestats.db` on the host.

## Configuration

Copy `.env.example` to `.env` and adjust the values:

| Variable                | Default              | Description                                                        |
| ----------------------- | -------------------- | ------------------------------------------------------------------ |
| `AGENT_API_KEY`         | `change-me`          | Shared secret for the agent and admin endpoints. Change it.        |
| `TIMEZONE`              | `Europe/Paris`       | Timezone used by the heatmap, daily totals, and "today" metrics.   |
| `STEAM_API_KEY`         | empty                | Steam Web API key.                                                 |
| `STEAM_ID`              | empty                | SteamID64 of the library owner.                                    |
| `IGDB_CLIENT_ID`        | empty                | Twitch application client ID.                                      |
| `IGDB_CLIENT_SECRET`    | empty                | Twitch application client secret.                                  |
| `FRONTEND_PORT`         | `8090`               | Host port for the dashboard.                                       |
| `BACKEND_PORT`          | `8091`               | Host port for the API (must be reachable by the agent).            |
| `AGENT_STALE_SECONDS`   | `180`                | Time without a heartbeat before an agent session is closed.        |
| `STEAM_SYNC_MINUTES`    | `15`                 | Steam synchronization interval.                                    |
| `IGDB_SYNC_MINUTES`     | `60`                 | IGDB enrichment interval.                                          |
| `SCHEDULER_ENABLED`     | `true`               | Set to `false` to disable background jobs.                         |
| `LOG_LEVEL`             | `INFO`               | Backend log level.                                                 |

Generate an agent key with:

```bash
openssl rand -hex 24
```

Use the same value in `.env` and in the agent configuration.

## Steam setup

Steam integration is optional; the dashboard still works with agent sessions
only.

1. Create a Steam Web API key: https://steamcommunity.com/dev/apikey
2. Find your SteamID64: https://steamid.io/
3. Make sure your profile and **game details** are public.
4. Set `STEAM_API_KEY` and `STEAM_ID` in `.env`, then run
   `docker compose up -d`.

The first synchronization records a baseline and does not create fake sessions.
Later synchronizations turn increases in total playtime into approximate Steam
sessions. Achievements are refreshed at most every six hours for recently played
games.

## IGDB setup

IGDB enrichment is optional.

1. Create a Twitch application: https://dev.twitch.tv/console/apps
2. Set `IGDB_CLIENT_ID` and `IGDB_CLIENT_SECRET` in `.env`.
3. Restart the backend.

Games without covers or genres are enriched in small batches (8 per hour by
default) so the Steam sync is never blocked by IGDB rate limits.

## Windows agent

Requirements: Python 3.10+ on Windows, on the same network as the backend.

```powershell
cd agent-windows
py -m pip install -r requirements.txt

# Send one heartbeat and exit
py tracker.py `
  --server http://192.168.1.20:8091 `
  --key "YOUR_AGENT_API_KEY" `
  --once

# Continuous tracking
py tracker.py `
  --server http://192.168.1.20:8091 `
  --key "YOUR_AGENT_API_KEY"
```

The agent also reads these environment variables:

- `GAMESTATS_URL`
- `GAMESTATS_API_KEY`
- `GAMESTATS_AGENT_ID`
- `GAMESTATS_INTERVAL`
- `GAMESTATS_LOG_FILE`

### Add a game

Edit `agent-windows/games.json` and map a display name to its executable(s):

```json
{
  "name": "My Game",
  "steam_app_id": 123456,
  "processes": ["mygame.exe", "mygame_dx12.exe"]
}
```

`steam_app_id` is optional but recommended: it merges the agent game with the
matching Steam entry. Restart the agent after editing the file. To find the exact
process name on Windows:

```powershell
Get-Process | Select-Object Name
```

### Start with Windows

Create a Task Scheduler task triggered **At log on**. Set the program to
`pythonw.exe` and use arguments like:

```text
"C:\GameStats\agent-windows\tracker.py" --server http://192.168.1.20:8091 --key "YOUR_KEY" --log-file "C:\GameStats\agent.log"
```

Run the task as the logged-in user, not as SYSTEM, otherwise game processes may
not be visible. Check the log file if nothing appears in the dashboard.

## API

| Method | Endpoint                  | Description                                      |
| ------ | ------------------------- | ------------------------------------------------ |
| `POST` | `/api/heartbeat`          | Agent heartbeat (`X-Agent-Key` header)           |
| `GET`  | `/api/stats/summary`      | Dashboard summary metrics                        |
| `GET`  | `/api/stats/heatmap`      | 7 × 24 heatmap (`?days=365`)                     |
| `GET`  | `/api/stats/daily`        | Daily totals (`?days=14`)                        |
| `GET`  | `/api/stats/top-games`    | Top games (`?days=30&limit=8`)                   |
| `GET`  | `/api/sessions`           | Recent sessions (`?limit=15`)                    |
| `GET`  | `/api/games`              | Library (`?search=&sort=playtime`)               |
| `GET`  | `/api/agents`             | Known agents and online state                    |
| `GET`  | `/api/health`             | Backend health                                   |
| `POST` | `/api/admin/sync/steam`   | Force a Steam sync (`X-Agent-Key`)               |
| `POST` | `/api/admin/enrich/igdb`  | Force IGDB enrichment (`X-Agent-Key`)            |

Interactive OpenAPI documentation is available at `/docs` on the backend port.

Force a Steam synchronization:

```bash
curl -X POST -H "X-Agent-Key: $AGENT_API_KEY" \
  http://localhost:8091/api/admin/sync/steam
```

Read endpoints are not authenticated. Do not expose the backend port directly to
the internet; keep the service behind a reverse proxy or restrict it to your LAN.

## Project layout

```text
gamestats/
├── compose.yml
├── .env.example
├── backend/
│   ├── main.py              # FastAPI app and routes
│   ├── heartbeat.py         # Agent session lifecycle
│   ├── stats.py             # Summary, daily, heatmap, top games
│   ├── scheduler.py         # Background jobs
│   ├── collectors/
│   │   ├── steam.py
│   │   └── igdb.py
│   └── tests/
├── frontend/
│   └── src/                 # React dashboard, sessions, library
└── agent-windows/
    ├── tracker.py
    └── games.json
```

## Development

### Backend

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements-dev.txt
cd backend
uvicorn main:app --reload --port 8000
```

Useful environment variables: `DATABASE_URL` (default
`sqlite:///./data/gamestats.db`), `AGENT_API_KEY`, `TIMEZONE`, and
`SCHEDULER_ENABLED=false` for local debugging without background jobs.

Run tests:

```bash
cd backend
pytest -q
```

### Frontend

```bash
cd frontend
npm install
npm run dev   # http://localhost:5173, /api proxied to localhost:8000
```

Production build:

```bash
npm run build
```

## Troubleshooting

- **401 on heartbeat** — the agent key and `AGENT_API_KEY` do not match.
- **Steam library is empty** — check that the profile and game details are
  public, and that `STEAM_ID` is a SteamID64. See `docker compose logs -f backend`.
- **No covers** — IGDB credentials are missing, invalid, or rate-limited. The
  backend logs the reason and retries later.
- **Session stuck as live** — the agent stopped responding; it is closed after
  `AGENT_STALE_SECONDS` (180 seconds by default).
- **Wrong hours in the heatmap** — fix `TIMEZONE` and restart the backend.
  Session timestamps are stored in UTC.
- **Game not detected** — check the exact process name in `games.json`. Java
  games often run under `javaw.exe` and need a dedicated rule.

## Security notes

- The agent and admin endpoints require the `X-Agent-Key` header.
- The default `AGENT_API_KEY` is `change-me`; always change it before exposing the
  service on a network.
- Read endpoints (dashboard, sessions, library) are intentionally unauthenticated.
  Restrict access to your LAN or add authentication at the reverse proxy.
- `.env`, the SQLite database, and local build artifacts are excluded from Git.

## Known limitations

- Steam playtime deltas are approximate: offline playtime is attributed to the
  synchronization window that detects the increase.
- The SQLite schema is created automatically; there are no Alembic migrations.
  To start over, stop the stack and remove the `data` directory.
- The current design targets a single PC agent. Multiple agents reporting the
  same game create separate sessions.
- The interface language is French; the code and documentation are in English.

## Changelog

See [CHANGELOG.md](CHANGELOG.md).
