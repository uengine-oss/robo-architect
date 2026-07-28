# Plan: Docker-managed Electron distribution

## Components

- `desktop/runtime/compose.yml`: fixed internal ports/network/health/dependencies.
- `desktop/runtime/docker/architect-api.Dockerfile`: release image가 아니라 runtime dependency
  audit와 server deployment 재사용을 위한 host API equivalent definition.
- `desktop/scripts/bundle-architect-runtime.ps1`: relocatable CPython + dependencies + source.
- `desktop/src/main/docker-stack.ts`: Docker preflight, offline load, compose up/reuse,
  explicit stop, health.
- `desktop/src/main/backend.ts`: dev host mode와 packaged Docker+bundled API mode의 explicit split.
- `desktop/electron-builder.yml`: runtime, Compose, image archive, manifest inclusion.

## Constitution check

- Determinism-first: runtime selection and manifest validation are deterministic; LLM 0.
- Single source: runtime manifest owns image tags, paths, and version.
- No silent failure: every child process exit and health timeout is surfaced and logged.
- Cross-service contracts: existing HTTP/Neo4j contracts remain; only deployment endpoints change.
- Secrets: generated at first run and never embedded in release artifacts.

## Data and path policy

- Neo4j data: Docker named volume, not installer directory.
- Analyzer shared upload data: named volume shared with ANTLR.
- Architect local project files: host API, unchanged Windows paths.
- Logs: Electron userData logs plus `docker compose logs` capture on failure.

## Verification

- unit tests for manifest/path/mode/command construction
- Electron TypeScript build
- Compose config
- image presence/archive verification
- packaged executable startup and API/UI probes
- quit/relaunch persistence probe
