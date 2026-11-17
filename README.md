# GameStats

Self-hosted gaming activity dashboard for your PC and Steam library. A small
Windows agent reports the games currently running, while the backend keeps a
history of sessions, synchronizes Steam playtime and achievements, and fetches
covers and genres from IGDB.

The interface ships in **French and English**, with **dark and light themes**.

Supported sources: **PC agent**, **Steam**, **Xbox** (achievements, gamerscore,
and recent games), **Ubisoft Connect** (games, dates, and session counts), **GOG**
(library and achievements), **Epic Games** (library and partial achievements),
and **IGDB** metadata. Optional enrichment adds **MobyGames** scores, **OpenCritic**
critic scores, and **HowLongToBeat** completion times.

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
- **Ubisoft Connect sync** — games played, first/last played dates, and session
  counts through the unofficial Ubisoft API. No Ubisoft password is stored; a
  manual remember-me ticket is used. Playtime and achievements are not provided.
- **GOG sync** — owned games, cover images, and achievement progress through the
  GOG Galaxy API, with an OAuth authorization-code connection. No GOG password is
  stored. GOG does not expose reliable playtime through its web API; PC playtime
  continues to come from the agent.
- **Epic Games sync** — owned games, catalog covers, and achievement progress
  where Epic exposes it, with an OAuth authorization-code connection. No Epic
  password is stored. Epic does not expose reliable playtime; PC playtime
  continues to come from the agent.
- **Double-count protection** — Steam playtime deltas already covered by an
  agent session are ignored.
- **IGDB enrichment** — HD covers and genres for games that do not have them yet.
- **Metadata enrichment** — MobyGames scores and fallback covers, OpenCritic
  critic scores and tiers, and HowLongToBeat community completion times. These
  providers are optional and run in the background.
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
  InfluxDB, Xbox, Ubisoft, GOG, and Epic Games integrations from the UI. Secrets
  are masked in responses.
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
  syncs Xbox every 30 minutes, syncs Ubisoft every 60 minutes, syncs GOG every
  60 minutes, syncs Epic Games every 120 minutes, and enriches metadata every
  360 minutes. Run a single uvicorn worker so the scheduler is not duplicated.
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

## Preview Docker images

The `Publish preview Docker images` workflow builds and pushes both images to
the GitHub Container Registry on every push to `main` (and on manual dispatch):

- `ghcr.io/lolo1580/gamestats-backend:preview-latest`
- `ghcr.io/lolo1580/gamestats-frontend:preview-latest`
- `ghcr.io/lolo1580/gamestats-backend:preview-YYYY-MM-DD-1`
- `ghcr.io/lolo1580/gamestats-frontend:preview-YYYY-MM-DD-1`

The dated tag uses the build date in the Europe/Paris timezone, for example
`preview-2026-11-17-1`. The packages are private by default: make them public in
the GitHub package settings, or authenticate before pulling:

```bash
echo "$GITHUB_TOKEN" | docker login ghcr.io -u YOUR_GITHUB_USER --password-stdin
```

There are two standalone Compose files:

| Mode | Command |
| --- | --- |
| Local build | `docker compose up -d --build` |
| Published preview images | `docker compose -f compose.preview.yml up -d` |

`compose.preview.yml` uses the same `.env` file and `./data` directory as the
local build. It is standalone: do not combine it with `compose.yml`.

Pull the latest preview images before starting:

```bash
docker compose -f compose.preview.yml pull
docker compose -f compose.preview.yml up -d
```

Set `GAMESTATS_IMAGE_TAG` to use a dated tag:

```bash
GAMESTATS_IMAGE_TAG=preview-2026-11-17-1 \
  docker compose -f compose.preview.yml up -d
```

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
| `UBISOFT_SYNC_MINUTES`  | `60`                 | Ubisoft synchronization interval.                                  |
| `GOG_SYNC_MINUTES`      | `60`                 | GOG synchronization interval.                                      |
| `EPIC_SYNC_MINUTES`     | `120`                | Epic Games synchronization interval.                               |
| `METADATA_SYNC_MINUTES` | `360`                | MobyGames/OpenCritic/HowLongToBeat enrichment interval.            |
| `METADATA_ENRICH_LIMIT` | `8`                  | Maximum games processed per metadata run.                          |
| `OPENCRITIC_ENRICH_LIMIT`| `4`                 | Maximum OpenCritic searches per run (free RapidAPI quota).         |
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

## Ubisoft setup

Ubisoft support uses the **unofficial Ubisoft Connect API**. It imports games
played, first/last played dates, and session counts. It does **not** import
playtime or achievements, and Ubisoft may change these endpoints without notice.

GameStats never receives your Ubisoft password. Obtain a `rememberMeTicket` with
your own login (for example with `curl`), then paste it into
**Settings → Intégrations → Ubisoft**:

```bash
curl -s https://public-ubiservices.ubi.com/v3/profiles/sessions \
  -H "Ubi-AppId: 4391c956-8943-48eb-8859-07b0778f47b9" \
  -H "Content-Type: application/json" \
  -H "Authorization: Basic $(printf 'EMAIL:PASSWORD' | base64)" \
  -d '{"rememberMe":true}'
```

Copy the `rememberMeTicket` field from the response. If your account requires
2FA, complete the Ubisoft 2FA flow first and then request a remember-me session.

The ticket is a sensitive credential. Store/transmit it only over a trusted
network or HTTPS, and disconnect the account in Settings if it is compromised.

## GOG setup

GOG support uses the **unofficial GOG Galaxy API** with the public Galaxy OAuth
client. It imports owned games, cover images, and achievement progress. GOG does
**not** expose reliable playtime through its web API, so PC playtime remains
measured by the agent.

Open **Settings → Intégrations → GOG**, click **Ouvrir la connexion GOG**, sign
in, then copy the `code` parameter from the redirect URL and paste it into the
authorization-code field. GameStats exchanges it for a refresh token, stores only
that token, and keeps it up to date automatically.

The GOG integration is unofficial and may need updates if GOG changes its API.
Disconnect the account in Settings to revoke the stored token.

## Epic Games setup

Epic support uses the **unofficial Epic Games launcher API** with the public
launcher OAuth client. It imports owned games, catalog covers, and achievement
progress where Epic exposes it. Epic does **not** expose reliable playtime, so PC
playtime remains measured by the agent.

Open **Settings → Intégrations → Epic Games**, click **Ouvrir la connexion Epic**,
sign in, then copy the `authorizationCode` value from the JSON page shown after
login (the whole page can also be pasted). GameStats exchanges it for a refresh
token, stores only that token, and keeps it up to date automatically.

The Epic integration is unofficial and may need updates if Epic changes its API.
Achievements are available only for supported games. Disconnect the account in
Settings to revoke the stored token.

## Metadata setup

GameStats can enrich games with data from three optional sources:

- **MobyGames** — score, vote count, release date, and fallback cover. Create a
  free non-commercial account, open your profile, and request an API key. The
  free tier is limited to about one request per second.
- **OpenCritic** — top-critic score, tier, review count, and recommendation
  percentage. Subscribe to the free OpenCritic API plan on RapidAPI and paste the
  RapidAPI key. Free quotas are limited, so GameStats processes only a few
  OpenCritic games per run.
- **HowLongToBeat** — community main-story, main-plus-extra, and completionist
  durations. No key is required; this uses the public website's search endpoint
  and is not an official API.

Enter the keys in **Settings → Intégrations → Métadonnées** and click
**Synchroniser les métadonnées**. The scheduler also runs the enrichment every
six hours.

**Giant Bomb is not integrated**: its official API no longer exposes game data
since 2026, so there is no reliable endpoint to query.

## Windows agent

### Installer

The recommended option is the Windows installer produced by the build workflow.
`GameStatsAgentSetup.exe` installs the agent per user, asks for the backend URL
and agent key, optionally starts it at sign-in, and creates Start Menu shortcuts
including a connection test. No administrator rights are required.

Build it on Windows with `agent-windows\build.ps1`, or run the
**Build Windows agent** GitHub Actions workflow and download the artifact. See
[agent-windows/README.md](agent-windows/README.md) for details.

The installer can also be served directly by the local GameStats server. Place
`GameStatsAgentSetup.exe` (and optionally `GameStatsAgent-portable.zip`) in the
`downloads/` directory at the repository root. The backend mounts it read-only
at `/downloads`, and the files become available in
**Settings → Général → Windows agent**. `agent-windows/build.ps1` copies new
builds there automatically. The binaries are ignored by Git.

The installed agent stores its configuration in `%APPDATA%\GameStats\agent.json`,
the watched games in `%APPDATA%\GameStats\games.json`, and its log in
`%APPDATA%\GameStats\agent.log`.

### Run from source

Requirements: Python 3.10+ on Windows, on the same network as the backend.
The agent key is available in **Settings → Général**.

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

- `GAMESTATS_SETTINGS` (default `%APPDATA%\GameStats\agent.json`)
- `GAMESTATS_URL`
- `GAMESTATS_API_KEY`
- `GAMESTATS_AGENT_ID`
- `GAMESTATS_INTERVAL`
- `GAMESTATS_CONFIG`
- `GAMESTATS_LOG_FILE`
- `GAMESTATS_LOG_LEVEL`

### Add a game

Edit `agent-windows/games.json` for source runs, or
`%APPDATA%\GameStats\games.json` for an installed agent, and map a display
name to its executable(s):

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

The installer creates a Startup shortcut by default. For a source run, create a
Task Scheduler task triggered **At log on**. Set the program to `pythonw.exe` and
use arguments like:

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
| `POST` | `/api/ubisoft/connect`   | Connect with a remember-me ticket (admin)        |
| `POST` | `/api/ubisoft/sync`      | Force a Ubisoft synchronization (admin)          |
| `POST` | `/api/ubisoft/disconnect`| Disconnect the Ubisoft account (admin)           |
| `GET`  | `/api/gog/auth-url`      | Read the GOG authorization URL (admin)           |
| `POST` | `/api/gog/connect`       | Connect with a GOG authorization code (admin)    |
| `POST` | `/api/gog/sync`          | Force a GOG synchronization (admin)              |
| `POST` | `/api/gog/disconnect`    | Disconnect the GOG account (admin)               |
| `GET`  | `/api/epic/auth-url`     | Read the Epic Games authorization URL (admin)    |
| `POST` | `/api/epic/connect`      | Connect with an Epic authorization code (admin)  |
| `POST` | `/api/epic/sync`         | Force an Epic Games synchronization (admin)      |
| `POST` | `/api/epic/disconnect`   | Disconnect the Epic Games account (admin)        |
| `POST` | `/api/metadata/sync`     | Enrich MobyGames/OpenCritic/HowLongToBeat (admin) |
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
├── compose.preview.yml
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
│   ├── routes_ubisoft.py    # Ubisoft ticket connection and sync
│   ├── collectors/ubisoft.py # Ubisoft Connect API client and parser
│   ├── routes_gog.py        # GOG OAuth connection and sync
│   ├── collectors/gog.py    # GOG Galaxy API client and parser
│   ├── routes_epic.py       # Epic Games OAuth connection and sync
│   ├── collectors/epic.py   # Epic Games API client and parser
│   ├── routes_metadata.py   # Metadata enrichment endpoint
│   ├── collectors/metadata.py # MobyGames, OpenCritic, HowLongToBeat clients
│   ├── heartbeat.py         # Agent session lifecycle
│   ├── stats.py             # Summary, daily, heatmap, top games
│   ├── scheduler.py         # Background jobs
│   ├── collectors/
│   │   ├── steam.py
│   │   └── igdb.py
│   └── tests/
├── agent-windows/
│   ├── tracker.py        # Process scanner and heartbeat client
│   ├── games.json        # Default game/process mappings
│   ├── GameStatsAgent.spec # PyInstaller build
│   ├── installer.iss     # Inno Setup installer
│   └── build.ps1         # Windows build script
├── downloads/            # Optional local agent downloads (binaries ignored)
└── frontend/
    └── src/                 # Auth, dashboard, settings, sessions, library
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
- The Ubisoft remember-me ticket is stored in SQLite, masked in API responses,
  and can be revoked by disconnecting the account.
- The GOG refresh token is stored in SQLite, masked in API responses, and can be
  revoked by disconnecting the account.
- The Epic Games refresh token is stored in SQLite, masked in API responses, and
  can be revoked by disconnecting the account.
- MobyGames and OpenCritic API keys are stored in SQLite and masked in API
  responses.
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
- Ubisoft support relies on an unofficial API and imports games, dates, and
  session counts only; playtime and achievements are not available.
- GOG support relies on an unofficial API and imports library and achievements
  only; playtime remains measured by the PC agent.
- Epic Games support relies on an unofficial launcher API. Achievements are
  partial, and playtime remains measured by the PC agent.
- OpenCritic uses the RapidAPI free tier by default, which limits how many games
  can be enriched per day.
- HowLongToBeat has no official public API; the enrichment uses its website
  search endpoint and may break if the site changes.
- Giant Bomb is not integrated because its games API is unavailable.
- Restoring a backup replaces users, games, sessions, settings, and invalidates
  current login sessions.
- InfluxDB exports are incremental and idempotent by point timestamp; changing
  the bucket or recreating the database does not automatically replay history.

## Changelog

See [CHANGELOG.md](CHANGELOG.md).
