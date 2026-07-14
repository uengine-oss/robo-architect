# Architect workspace script integration

## Goal

Make the repository's Windows development and build entry points reliable by
delegating multi-repository orchestration to the shared `robo-workspace` engine.

## Requirements

- Preserve `scripts/dev-desktop.cmd` and `scripts/build-desktop-app.cmd` as easy
  Windows entry points.
- Do not run nested Analyzer submodules or kill arbitrary port/Electron owners.
- Resolve the workspace by `ROBO_WORKSPACE_DIR` first and by the normal sibling
  layout second; emit an actionable error if neither exists.
- Build the Analyzer remote from `ROBO_ANALYZER_FRONTEND_DIR` when supplied.
- Preserve `-SkipBuild`, `-NoElectron`, `-Stop`, `-Installer`, and
  `-SkipFrontend` compatibility with explicit mappings.
- Package `frontend/dist` as an external Electron resource so the unpacked app
  does not open to a missing page.
- Resolve the development backend from `ROBO_BACKEND_DIR` or a verified
  `api/main.py` ancestor, never a machine-specific absolute path.
- Keep Windows development packages unsigned until a real signing certificate
  is configured; do not download a signing toolchain and pretend to sign.
