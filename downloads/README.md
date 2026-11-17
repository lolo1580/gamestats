# Agent downloads (optional override)

The Docker preview backend image already bundles the latest Windows agent from
the **Build Windows agent** GitHub Actions artifact. Files placed here are used
first and override the bundled copy at `/opt/agent-downloads`.

For source runs, the backend reads this directory by default. Place:

- `GameStatsAgentSetup.exe` — recommended installer;
- `GameStatsAgent-portable.zip` — optional portable version.

The files are served through **Settings → General → Windows agent**. Binaries in
this directory are ignored by Git.
