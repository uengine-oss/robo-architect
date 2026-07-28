# Plan: Docker-managed Electron distribution

## Components

- `desktop/runtime/compose.yml`: fixed internal ports/network/health/dependencies.
- `desktop/runtime/docker/architect-api.Dockerfile`: release image가 아니라 runtime dependency
  audit와 server deployment 재사용을 위한 host API equivalent definition.
- `desktop/scripts/bundle-architect-runtime.ps1`: relocatable CPython + dependencies + source.
- `desktop/src/main/docker-stack.ts`: Docker preflight, offline load, compose up/reuse,
  explicit stop, health.
- `desktop/src/main/backend.ts`: dev host mode와 packaged Docker+bundled API mode의 explicit split.
- `desktop/src/main/fs-browser.ts`: selected Windows project를 Gateway multipart ingress로
  전달하는 host/container bridge. 파일 분류 자체는 Parser 단일 진실을 유지한다.
- `desktop/electron-builder.yml`: runtime, Compose, image archive, manifest inclusion.
- `desktop/resources/runtime/config/*.env`: Workspace release가 생성하는 service-scoped
  environment snapshots. Compose는 서비스별 파일만 읽고 topology 값은 명시적으로 override.

## Constitution check

- Determinism-first: runtime selection and manifest validation are deterministic; LLM 0.
- Single source: runtime manifest owns image tags, paths, and version.
- No silent failure: every child process exit and health timeout is surfaced and logged.
- Cross-service contracts: existing HTTP/Neo4j contracts remain; only deployment endpoints change.
- Secrets: Neo4j password는 첫 실행에 생성한다. 내부 GPU/API credential은 사용자가 요구한
  즉시 실행형 사내 배포를 위해 release-time snapshot으로 installer에 포함되며 Git,
  manifest JSON, 로그에는 값이 남지 않는다. 설치 파일을 받은 사용자는 이를 추출할 수
  있으므로 이 배포물은 내부 배포로 취급한다.

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
- service env checksum/config construction verification
- Windows path ingress → Parser content classification verification with shop_mall
- packaged executable startup and API/UI probes
- quit/relaunch persistence probe
- packaged Gateway/Data Fabric → PostgreSQL connection, registry, metadata, sample query verification
- pinned MindsDB image/archive identity, named volume, health dependency, and internal-only Fabric routing
