# Bundled agent downloads

This directory is baked into the backend Docker image at
`/opt/agent-downloads`. The Docker preview workflow fills it from the latest
successful **Build Windows agent** artifact before building the image.

The root `downloads/` directory remains an optional host override for local or
source deployments. Binaries in both directories are ignored by Git.
