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
  │    ├─ MindsDB
  │    ├─ ANTLR Parser
  │    └─ API Gateway
  └─ bundled Vue host + Analyzer federation assets
```

Architect API는 로컬 project root와 Claude CLI/PTY를 사용해야 하므로 host sidecar로
유지한다. 나머지 서비스는 Docker network 내부 이름으로 통신한다.

## Contracts

- packaged mode는 `resources/runtime/runtime-manifest.json`이 있어야 한다.
- runtime manifest schema v3는 app-owned MindsDB image identity를 필수로 포함한다.
- packaged mode는 manifest가 고정한 서비스별 환경 파일을 읽어야 한다. Analyzer,
  Catalog, Data Fabric, Architect API는 개발 checkout의 `.env`나 설치 PC의 셸 환경에
  의존하지 않는다.
- Analyzer는 `ROBO_LLM_CONFIG=qwen36_sglang_local`과 해당 API key를 함께 받아
  `llm/configs/qwen36_sglang_local.yaml`에 고정된 GPU endpoint/model을 사용한다.
- 서비스별 환경 파일에는 그 서비스가 소비하는 키만 들어간다. Docker 내부 주소,
  app-owned Neo4j 인증, 공유 `/data`, 동적 host port는 패키지 환경보다 Compose/Electron
  런타임 값이 항상 우선한다.
- Architect API는 bundled app root의 `.env`를 읽고, app-owned Neo4j 연결은 child
  process 환경으로 다시 덮어쓴다.
- Electron의 Windows 폴더 선택 경로를 Linux Parser container에 그대로 넘기지 않는다.
  Electron main이 선택 루트 아래 일반 파일을 경로 보존 multipart로 Gateway에 반입한 뒤
  Parser를 upload mode로 실행한다. Parser가 `.sql` 내용을 검사해 table/view/index/sequence
  정의는 `data/ddl`, routine/package/trigger/type 또는 그 밖의 파일은 `data/source`로
  분류한다.
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
- packaged layout에 service-scoped env files와 Architect API `.env`가 존재하고 manifest
  checksum과 일치한다.
- Analyzer container의 effective environment로 LLM client를 만들었을 때 provider는
  `sglang`, endpoint는 사내 GPU endpoint, model은 `frentis-ai-model`이다.
- `shop_mall` 코드와 schema DDL이 함께 있는 Windows 폴더를 고르면 C source 12개와
  schema DDL 1개가 container 공유 volume의 서로 다른 canonical root로 반입된다.
- Docker daemon 미실행, archive 손상, health timeout, API crash가 서로 구분된 오류가 된다.
- normal startup/retry/shutdown에서 고아 local API가 없고, container는 manifest가 식별한
  앱 소유 Compose project로만 남는다.
- existing dev mode는 Workspace의 `ROBO_BACKEND_DIR` + `uv` 흐름을 유지한다.
- 격리된 PostgreSQL datasource를 packaged Gateway/Data Fabric으로 연결 검사·등록·metadata
  추출·조회할 수 있고, datasource registry는 app-owned Neo4j에 보존된다.
- Data Fabric은 설치 PC의 기존 MindsDB나 host port에 의존하지 않고 app-owned
  `mindsdb/mindsdb:v26.1.0` service를 Docker network로 사용한다.
