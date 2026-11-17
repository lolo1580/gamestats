# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- First-run administrator setup, login/logout, and local browser sessions.
- User management with `admin` and `viewer` roles, account activation, password
  resets, and last-admin safeguards.
- Argon2 password hashing and hashed session tokens stored in SQLite.
- Database-backed settings for timezone, agent key, Steam, and IGDB credentials,
  with masked secret values in API responses.
- Agent key reveal and rotation from the settings UI.
- Protected Swagger UI and ReDoc pages.
- Settings interface with General, Integrations, Users, Account, Backups, and
  Documentation sections.
- User menu with account, settings, API documentation, and logout actions.
- JSON and SQLite database backups with download and restore from the admin
  settings page.
- Snapshot validation, active-admin safeguard, and automatic session invalidation
  after a restore.
- French / English interface with a header language switch, localized dates,
  numbers, and labels. Language preference is stored in the browser and on the
  user account.
- `PATCH /api/auth/me` support for updating the account locale.
- Token-protected JSON API for the gethomepage.dev `customapi` widget, with
  token generation, reveal, and rotation.
- InfluxDB v2 export of session points and summary metrics, scheduled every
  15 minutes and available on demand, with a stored export watermark.
- InfluxDB and Homepage settings sections with masked tokens and integration
  status.
- Xbox integration via passwordless Azure device-code flow, with achievements,
  gamerscore, recent games, cover images, and a 30-minute sync.
- Xbox-specific game fields and library badges, plus a disconnect action.
- Ubisoft Connect integration with a manual remember-me ticket, games played,
  first/last dates, session counts, and library badges.
- GOG integration with an OAuth authorization-code connection, owned games,
  covers, achievement progress, library badges, and a 60-minute sync.
- Epic Games integration with an OAuth authorization-code connection, owned
  games, catalog covers, partial achievements, library badges, and a 120-minute
  sync.
- Metadata enrichment with MobyGames scores and covers, OpenCritic critic scores,
  and HowLongToBeat completion times, configurable from the settings page with
  a manual sync.
- Windows agent packaging with a PyInstaller executable, an Inno Setup installer
  that asks for the backend URL and agent key, optional sign-in startup, a
  connection test, and a GitHub Actions build workflow.
- JSON settings support for the Windows agent, with per-user configuration,
  games list, and log files under `%APPDATA%\GameStats`.
- GitHub Actions workflow that publishes backend and frontend preview images to
  GHCR with `preview-latest` and `preview-YYYY-MM-DD-1` tags, plus a standalone
  `compose.preview.yml` file for running the published images.
- Local agent download from the GameStats server: files placed in `downloads/`
  are served by the backend and exposed in Settings → General. Preview Docker
  images automatically bundle the latest Windows agent artifact.
- `--list-processes` diagnostic in the Windows agent, which lists running
  executables and flags the ones already watched, to help fill `games.json`.

### Changed

- Settings integrations now cover Steam, IGDB, Homepage, InfluxDB, Xbox,
  Ubisoft, GOG, Epic Games, and optional metadata providers.
- The SQLite schema now migrates new platform and metadata columns on existing
  game tables.
- Compose now loads backend settings directly from `.env`; `compose.preview.yml`
  is a standalone file for the published GHCR images and uses the same data
  directory.
- Preview Compose services always pull the latest image; `index.html` is served
  with `no-cache`, and `/api/health` exposes the backend version.
- Dashboard, library, sessions, stats, agents, user, and settings endpoints now
  require an authenticated session.
- Admin sync/enrichment endpoints now require an administrator session instead
  of the agent key.
- Steam and IGDB scheduled jobs always run and skip cleanly while integrations
  are unconfigured, so settings changes apply without a restart.
- Integration credentials and the agent key can be updated without restarting
  the backend.
- Settings page now includes Backups and Documentation tabs.
- README and changelog are maintained in English.
- The Windows agent now keeps running after an unexpected error in its cycle,
  retries an unreachable backend with capped exponential backoff, rotates its
  log file, reports ignored `games.json` entries, and sends its real version in
  the `User-Agent` header.

### Security

- Session cookies are HttpOnly and SameSite=Lax; `COOKIE_SECURE` enables the
  Secure flag for HTTPS deployments.
- Integration secrets are stored in SQLite and never returned unmasked.
- Read endpoints are no longer public.
- Backups contain password hashes and integration secrets and must be stored
  securely.

## [1.0.0] - 2026-11-17

### Added

- FastAPI backend with SQLite persistence for games, sessions, playtime
  snapshots, achievements, and agent state.
- Real-time session lifecycle driven by agent heartbeats, including automatic
  closure after an inactivity timeout.
- Windows tracking agent based on `psutil`, with configurable process mappings,
  stable agent IDs, structured logs, and one-shot mode for diagnostics.
- Steam collector for owned games, total and two-week playtime, last played
  dates, and achievement progress.
- Steam playtime delta sessions with overlap detection to avoid double-counting
  time already measured by the agent.
- IGDB collector for HD covers and genres, including Twitch OAuth token caching
  and rate-limit-friendly batch enrichment.
- APScheduler jobs for stale session cleanup, Steam synchronization, and IGDB
  enrichment.
- Dashboard with summary metrics, a 14-day activity chart, live session card,
  annual 7 × 24 heatmap, top games, and recent sessions.
- Session history page with source filters, text search, and day grouping.
- Library page with search, sorting, Steam playtime, recent playtime, and
  achievement progress.
- Light and dark themes with a header switch, browser persistence, and no
  flash of the wrong theme on reload.
- Responsive layouts for desktop, tablet, and mobile.
- Docker Compose stack with a Python backend, SQLite volume, nginx frontend, and
  backend healthcheck.
- Agent-key authentication for heartbeat, Steam sync, and IGDB admin endpoints.
- Backend test suite covering heartbeat authentication, session lifecycle,
  library matching, daily totals, heatmap, top games, and recent sessions.
- Docker, agent, API, configuration, troubleshooting, and security documentation.

### Security

- `.env`, SQLite data, dependency directories, and build artifacts are excluded
  from Git.
- The backend warns when the default `AGENT_API_KEY` is still in use.
- Read endpoints remain unauthenticated by design and should be protected with
  network restrictions or a reverse proxy.
