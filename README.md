# GameStats

Self-hosted gaming activity dashboard for your PC and Steam library. A small
Windows agent reports the games currently running, while the backend keeps a
history of sessions, synchronizes Steam playtime and achievements, and fetches
covers and genres from IGDB.

The interface ships in **French and English**, with **dark and light themes**.

Supported sources: **PC agent**, **Steam**, **Xbox** (achievements, gamerscore,
and recent games), and **IGDB** metadata.

## Features

- **Real-time sessions** — the Windows agent sends a heartbeat every 30 seconds;
  the backend opens, extends, and closes game sessions automatically.
- **Dashboard** — key metrics, a 14-day activity chart, a live session card, an
  annual heatmap, top games, and recent sessions.
- **Steam library sync** — owned games, total and two-week playtime, last played
  dates, and achievement progress. Playtime deltas become approximate sessions.
- **Xbox library sync** — achievements, gamerscore, and recent games through the
  Xbox Web API, with a passwordless Azure device-code connection. Xbox does not
  expose reliable per-game playtime; PC playtime continues to come from the
  agent.
- **Double-count protection** — Steam playtime deltas already covered by an
  agent session are ignored.
- **IGDB enrichment** — HD covers and genres for games that do not have them yet.
- **Session history** — filter by source (PC agent or Steam), search by game,
  and group sessions by day.
- **Library** — search, sort, inspect playtime and achievement progress.
- **Light / dark theme** — switch from the header; the preference is stored in
  the browser and applied before the first render.
- **French / English interface** — switch from the header; the preference is
  stored in the browser and on the user account.
- **Accounts and roles** — first-run admin setup, login/logout, local sessions,
  user management, and `admin` / `viewer` roles.
- **Backend settings** — manage the agent key, timezone, Steam, IGDB, Homepage,
  InfluxDB, and Xbox integration from the UI. Secrets are masked in responses.
- **Backups** — export a readable JSON snapshot or a full SQLite database, then
  restore either format from the settings page.
- **Homepage widget API** — a token-protected JSON endpoint ready for the
  gethomepage.dev `customapi` widget.
- **InfluxDB v2 export** — scheduled or manual export of sessions and summary
  metrics with a dedicated token.
- **Protected documentation** — Swagger UI and ReDoc require an authenticated
  session, just like the dashboard.
- **Docker Compose** — backend, SQLite persistence, and an nginx-served frontend.
- **Authentication** — write endpoints are protected by an agent API key and the
  web UI is protected by user sessions.

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
  enriches IGDB data every 60 minutes, exports InfluxDB points every 15 minutes,
  and syncs Xbox every 30 minutes. Run a single uvicorn worker so the scheduler
  is not duplicated.
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

On first launch, open the dashboard and create the administrator account. There
is no default password. The Swagger and ReDoc pages require this session too.

## Configuration

Copy `.env.example` to `.env` and adjust the values:

| Variable                | Default              | Description                                                        |
| ----------------------- | -------------------- | ------------------------------------------------------------------ |
| `AGENT_API_KEY`         | `change-me`          | Initial agent secret. Editable in Settings.                        |
| `TIMEZONE`              | `Europe/Paris`       | Initial timezone. Editable in Settings.                            |
| `STEAM_API_KEY`         | empty                | Initial Steam Web API key. Editable in Settings.                   |
| `STEAM_ID`              | empty                | Initial SteamID64. Editable in Settings.                           |
| `IGDB_CLIENT_ID`        | empty                | Initial Twitch client ID. Editable in Settings.                    |
| `IGDB_CLIENT_SECRET`    | empty                | Initial Twitch client secret. Editable in Settings.                |
| `XBOX_CLIENT_ID`        | empty                | Azure application client ID for the Xbox device-code flow.         |
| `FRONTEND_PORT`         | `8090`               | Host port for the dashboard.                                       |
| `BACKEND_PORT`          | `8091`               | Host port for the API (must be reachable by the agent).            |
| `AGENT_STALE_SECONDS`   | `180`                | Time without a heartbeat before an agent session is closed.        |
| `STEAM_SYNC_MINUTES`    | `15`                 | Steam synchronization interval.                                    |
| `IGDB_SYNC_MINUTES`     | `60`                 | IGDB enrichment interval.                                          |
| `INFLUX_EXPORT_MINUTES` | `15`                 | InfluxDB export interval.                                          |
| `XBOX_SYNC_MINUTES`     | `30`                 | Xbox synchronization interval.                                     |
| `SESSION_DAYS`          | `7`                  | Browser session lifetime, in days.                                |
| `COOKIE_SECURE`         | `false`              | Set to `true` when serving the app over HTTPS.                     |
| `SCHEDULER_ENABLED`     | `true`               | Set to `false` to disable background jobs.                         |
| `LOG_LEVEL`             | `INFO`               | Backend log level.                                                 |

Environment values seed the database on first start. Integration credentials and
the agent key can then be changed in **Settings** without restarting the stack.

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
4. Set `STEAM_API_KEY` and `STEAM_ID` in **Settings → Intégrations** (or seed
   them in `.env` before the first start).

The first synchronization records a baseline and does not create fake sessions.
Later synchronizations turn increases in total playtime into approximate Steam
sessions. Achievements are refreshed at most every six hours for recently played
games.

## IGDB setup

IGDB enrichment is optional.

1. Create a Twitch application: https://dev.twitch.tv/console/apps
2. Set `IGDB_CLIENT_ID` and `IGDB_CLIENT_SECRET` in **Settings → Intégrations**
   (or seed them in `.env` before the first start).

Enrichment starts with the next scheduled job; no restart is required.

Games without covers or genres are enriched in small batches (8 per hour by
default) so the Steam sync is never blocked by IGDB rate limits.

## Xbox setup

Xbox support is optional and does **not** import playtime: the Xbox API does not
expose reliable per-game playtime. It imports achievements, gamerscore, recent
games, and cover images where available. PC playtime is still measured by the
Windows agent.

1. In the Microsoft Entra admin center, create an **App registration**.
2. Choose an account type that supports **personal Microsoft accounts**.
3. Under **Authentication**, enable **Allow public client flows** (device code).
4. Copy the **Application (client) ID** into **Settings → Intégrations → Xbox**
   (or set `XBOX_CLIENT_ID` before the first start).
5. Save, click **Connect Xbox**, open `https://microsoft.com/link`, and enter
   the displayed code. Approve the `XboxLive.signin` and
   `XboxLive.offline_access` scopes.
6. GameStats stores only a refresh token and automatically syncs every
   30 minutes.

The connection can be revoked from the Xbox section of the settings page.

## Windows agent

Requirements: Python 3.10+ on Windows, on the same network as the backend.
The agent key is available in **Settings → Général** (it can also be seeded with
`AGENT_API_KEY` before the first start).

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
| `POST` | `/api/auth/setup`         | Create the first administrator                   |
| `POST` | `/api/auth/login`         | Start a browser session                          |
| `POST` | `/api/auth/logout`        | End the current session                          |
| `GET`  | `/api/auth/me`            | Current user                                     |
| `PATCH` | `/api/auth/me`           | Update locale preference                         |
| `POST` | `/api/auth/password`      | Change your own password                         |
| `GET`  | `/api/users`              | List users (admin)                               |
| `POST` | `/api/users`              | Create a user (admin)                            |
| `PATCH` | `/api/users/{id}`         | Update a user (admin)                            |
| `DELETE` | `/api/users/{id}`        | Delete a user (admin)                            |
| `GET`  | `/api/settings`           | Read masked settings (admin)                     |
| `PATCH` | `/api/settings`           | Update integrations and timezone (admin)         |
| `GET`  | `/api/settings/agent-key` | Reveal the agent key (admin)                     |
| `POST` | `/api/settings/agent-key/rotate` | Rotate the agent key (admin)              |
| `GET`  | `/api/admin/backup/export/json`  | Download a JSON backup (admin)            |
| `GET`  | `/api/admin/backup/export/sqlite`| Download a SQLite backup (admin)          |
| `POST` | `/api/admin/backup/import/json`  | Restore a JSON backup (admin)             |
| `POST` | `/api/admin/backup/restore/sqlite` | Restore a SQLite backup (admin)         |
| `GET`  | `/api/homepage`          | Homepage widget JSON (`X-API-Key` or token)      |
| `POST` | `/api/admin/influxdb/export` | Export sessions and metrics to InfluxDB     |
| `POST` | `/api/xbox/device-code`  | Start the Xbox device-code flow (admin)          |
| `POST` | `/api/xbox/device-code/poll` | Poll/complete the Xbox connection (admin)    |
| `POST` | `/api/xbox/sync`         | Force an Xbox synchronization (admin)            |
| `POST` | `/api/xbox/disconnect`   | Disconnect the Xbox account (admin)              |
| `POST` | `/api/admin/sync/steam`   | Force a Steam sync (admin session)               |
| `POST` | `/api/admin/enrich/igdb`  | Force IGDB enrichment (admin session)            |

Interactive OpenAPI documentation is available at `/docs` and `/redoc`. Both
require a logged-in session. Dashboard and library endpoints also require a
session; only `/api/health`, authentication routes, and the agent heartbeat are
public.

### Homepage integration

Generate a **Homepage token** in **Settings → Intégrations**, then add a
`customapi` widget to gethomepage.dev:

```yaml
- GameStats:
    widget:
      type: customapi
      url: http://YOUR-HOST:8090/api/homepage
      refreshInterval: 60000
      headers:
        X-API-Key: YOUR_HOMEPAGE_TOKEN
      mappings:
        - field: active_games
          label: In game
        - field: week
          label: This week
        - field: today
          label: Today
        - field: library_count
          label: Games
```

The token can also be passed as `?token=...`, but the header is preferred.

### InfluxDB export

In **Settings → Intégrations**, configure the InfluxDB v2 URL, token,
organization, bucket, and enable automatic export. The scheduler exports:

- `gamestats_session` points with `game`, `source`, `game_id`, and
  `duration_seconds`;
- one `gamestats_summary` point per run with daily, weekly, total, session, and
  library metrics.

Use **Export now** to trigger a manual run. The last successful export timestamp
is stored in the database.

Force a Steam synchronization with an admin session:

```bash
curl -c /tmp/gamestats-cookies.txt -X POST \
  -H "Content-Type: application/json" \
  -d '{"identifier":"admin","password":"YOUR_PASSWORD"}' \
  http://localhost:8091/api/auth/login

curl -b /tmp/gamestats-cookies.txt -X POST \
  http://localhost:8091/api/admin/sync/steam
```

Do not expose the backend port directly to the internet; keep the service behind
a reverse proxy or restrict it to your LAN.

## Project layout

```text
gamestats/
├── compose.yml
├── .env.example
├── backend/
│   ├── main.py              # FastAPI app and routes
│   ├── security.py          # Sessions, password hashing, role checks
│   ├── settings_service.py  # DB-backed settings and masking
│   ├── routes_auth.py       # Setup, login, logout, account
│   ├── routes_users.py      # User management
│   ├── routes_settings.py   # Integration settings
│   ├── routes_backup.py     # JSON/SQLite backup and restore
│   ├── routes_homepage.py   # gethomepage.dev widget API
│   ├── routes_influx.py     # Manual InfluxDB export
│   ├── influx.py            # InfluxDB line-protocol exporter
│   ├── routes_xbox.py       # Xbox device-code connection and sync
│   ├── collectors/xbox.py   # Xbox Live API client and parser
│   ├── heartbeat.py         # Agent session lifecycle
│   ├── stats.py             # Summary, daily, heatmap, top games
│   ├── scheduler.py         # Background jobs
│   ├── collectors/
│   │   ├── steam.py
│   │   └── igdb.py
│   └── tests/
├── frontend/
│   └── src/                 # Auth, dashboard, settings, sessions, library
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

- **401 on heartbeat** — the agent key does not match the key in
  **Settings → Général**.
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

- Dashboard, library, session, user, settings, Swagger, and ReDoc endpoints
  require an authenticated browser session.
- The agent heartbeat uses the `X-Agent-Key` header. The key is managed in
  **Settings** and can be rotated at any time.
- Admin endpoints require an `admin` account. `viewer` accounts are read-only.
- Passwords are hashed with Argon2. Session tokens are random, stored hashed in
  SQLite, and sent in an HttpOnly, SameSite=Lax cookie.
- Set `COOKIE_SECURE=true` when the app is served over HTTPS.
- Integration secrets are stored in SQLite and masked in API responses. Protect
  the `data` directory and backups accordingly. Backups include password hashes
  and integration secrets; store them securely.
- Homepage and InfluxDB tokens are stored in SQLite and masked in API responses.
- The Xbox refresh token is stored in SQLite, masked in API responses, and can
  be revoked by disconnecting the account.
- The default `AGENT_API_KEY` is `change-me`; change it before exposing the
  service on a network.
- `.env`, the SQLite database, and local build artifacts are excluded from Git.

## Known limitations

- Steam playtime deltas are approximate: offline playtime is attributed to the
  synchronization window that detects the increase.
- The SQLite schema is created automatically; there are no Alembic migrations.
  To start over, stop the stack and remove the `data` directory.
- The current design targets a single PC agent. Multiple agents reporting the
  same game create separate sessions.
- Xbox data does not include reliable playtime; only achievements, gamerscore,
  and recent games are synchronized.
- Restoring a backup replaces users, games, sessions, settings, and invalidates
  current login sessions.
- InfluxDB exports are incremental and idempotent by point timestamp; changing
  the bucket or recreating the database does not automatically replay history.

## Changelog

See [CHANGELOG.md](CHANGELOG.md).
