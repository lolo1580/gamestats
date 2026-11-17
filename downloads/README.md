# Agent downloads

Place the Windows agent files in this directory to make them available from the
GameStats web interface under **Settings → General → Windows agent**:

- `GameStatsAgentSetup.exe` — recommended installer;
- `GameStatsAgent-portable.zip` — optional portable version.

The files are served by the backend from `/downloads` in Docker and are ignored
by Git. Build them with `agent-windows/build.ps1` (Windows) or download the
artifact produced by the **Build Windows agent** GitHub Actions workflow.
