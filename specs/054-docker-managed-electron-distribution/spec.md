# Docker-managed Electron distribution

## Goal

Robo Architect Electron installer가 host checkout과 개발 도구에 의존하지 않고,
Docker Desktop만 있는 Windows x64 사용자에게 전체 제품 stack을 제공한다.

## Runtime topology

```text
Electron main
  ├─ bundled CPython → host Architect API
  ├─ docker compose
  │    ├─ Neo4j (named volume)
  │    ├─ Analyzer
  │    ├─ Catalog
  │    ├─ Data Fabric
  │    ├─ ANTLR Parser
  │    └─ API Gateway
  └─ bundled Vue host + Analyzer federation assets
```

Architect API는 로컬 project root와 Claude CLI/PTY를 사용해야 하므로 host sidecar로
유지한다. 나머지 서비스는 Docker network 내부 이름으로 통신한다.

## Contracts

- packaged mode는 `resources/runtime/runtime-manifest.json`이 있어야 한다.
- image archive version marker가 없으면 `docker load`; 있으면 재사용한다.
- Compose project name은 user 단위로 고정하고 다른 Compose project를 건드리지 않는다.
- Neo4j password는 첫 실행에 생성해 OS secure store에 보존하고 로그에 남기지 않는다.
- host connection URI는 `bolt://127.0.0.1:<port>`, container connection URI는
  `bolt://neo4j:7687`로 분리한다.
- local Architect API는 bundled Python만 사용하며 `uv`, host Python, source checkout으로
  폴백하지 않는다.
- app 종료는 host Architect API만 내린다. Compose container는 warm 상태로 재사용한다.
  명시적인 engine stop만 `docker compose stop`을 호출하며 named volume은 보존한다.

## Acceptance

- clean packaged layout에서 `api/main.py`, bundled Python, Compose, archive가 모두 존재한다.
- Docker daemon 미실행, archive 손상, health timeout, API crash가 서로 구분된 오류가 된다.
- normal startup/retry/shutdown에서 고아 local API가 없고, container는 manifest가 식별한
  앱 소유 Compose project로만 남는다.
- existing dev mode는 Workspace의 `ROBO_BACKEND_DIR` + `uv` 흐름을 유지한다.
