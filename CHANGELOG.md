# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Nothing yet.

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
