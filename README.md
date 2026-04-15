# Robo Architect (MSAez) — Ontology-driven Event Storming Navigator

요구사항/유저스토리의 변화가 시스템 전체(BC/Command/Event/Policy/ReadModel 등)에 어떻게 전파되는지 **Neo4j 그래프 기반으로 탐색·분석·계획**하는 도구입니다.

- **Backend**: FastAPI (`api/`) — Neo4j + LLM 기반 인제스션/변경관리/PRD 생성 API
- **Frontend**: Vue + Vite (`frontend/`) — Event Storming 캔버스/네비게이터 UI
- **Docs/Cypher**: `docs/cypher/` — 스키마/샘플데이터/쿼리 모음

**Demo Video**
🎥 [Code Generation from Legacy Analysis](https://youtu.be/NtIHSZHugpU?si=xQTYBPEHXdTDrO6B)
🎥 [Legacy Analysis](https://youtu.be/9s54dhhERM0?si=GUj-b7NZ2TLLuF6y)
🎥 [Figma & JIRA Integration](https://youtu.be/CHw9U1aQZFg?si=PmLI1R8o4zaDxfze)

---

## 목차

- [빠른 시작](#빠른-시작)
- [주요 기능](#주요-기능)
- [API 개요](#api-개요)
- [그래프(Neo4j) 스키마](#그래프neo4j-스키마)
- [CLI (옵션)](#cli-옵션)
- [프로젝트 구조](#프로젝트-구조)
- [라이선스](#라이선스)

---

## 빠른 시작

### 사전 요구사항

- **Python**: 3.11+
- **Node.js**: 20+ (권장 22+)
- **Neo4j**: 4.4+ (권장 5.x)
- **(선택)** `cypher-shell` (스키마/샘플 데이터 적용용)

### 1) 환경변수 설정

이 프로젝트는 `.env.example`를 기준으로 `.env`를 구성합니다.

#### Windows (PowerShell)

```powershell
Copy-Item .\.env.example .\.env
```

#### macOS/Linux

```bash
cp .env.example .env
```

`.env`에서 최소한 아래를 설정하세요.

- **Neo4j**: `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` (필요 시 `NEO4J_DATABASE`)
- **LLM**: `LLM_PROVIDER`, `LLM_MODEL`, 그리고 해당 키(`OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `GOOGLE_API_KEY`)

### 2) Neo4j 스키마 적용 (최초 1회)

Cypher 스키마 파일은 `docs/cypher/schema/`에 있습니다.

```bash
cypher-shell -f docs/cypher/schema/01_constraints.cypher
cypher-shell -f docs/cypher/schema/02_indexes.cypher
```

#### (선택) 샘플 데이터 로드

```bash
cypher-shell -f docs/cypher/sample_data.cypher
```

### 3) 백엔드 실행 (FastAPI)

#### uv 사용 (권장)

```bash
uv sync
uv run uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

#### pip 사용 (대안)

```bash
python -m pip install -r requirements.txt
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

### 4) 프론트엔드 실행 (Vue/Vite)

```bash
cd frontend
npm install
npm run dev
```

`frontend/vite.config.js`에서 `/api`를 `http://localhost:8000`으로 프록시하므로, 개발 중에는 프론트에서 그대로 `/api/...` 호출이 가능합니다.

### 5) 접속 URL

- **Frontend**: `http://localhost:5173`
- **Backend**: `http://localhost:8000`
- **Swagger(OpenAPI)**: `http://localhost:8000/docs`
- **Health check**: `GET /api/health`

---

## 주요 기능

### 1) 요구사항 인제스션 (텍스트/PDF) + 실시간 진행률(SSE)

- 문서 업로드/텍스트 입력 → LLM 기반 파이프라인 실행 → Neo4j에 모델 저장
- SSE로 진행률 스트리밍 제공

대표 API:
- `POST /api/ingest/upload`
- `GET /api/ingest/stream/{session_id}`
- `POST /api/ingest/{session_id}/pause`, `POST /api/ingest/{session_id}/resume`
- `DELETE /api/ingest/clear-all` (주의: Neo4j 전체 삭제)

### 2) 캔버스 그래프 탐색 (Canvas Graph)

- 서브그래프 조회/확장/이벤트 트리거 관계 조회/관계 탐색

대표 API:
- `GET /api/graph/subgraph`
- `GET /api/graph/expand/{node_id}`
- `GET /api/graph/expand-with-bc/{node_id}`
- `GET /api/graph/event-triggers/{event_id}`
- `GET /api/graph/stats`, `DELETE /api/graph/clear`

### 3) 컨텍스트(BC) 트리 탐색

대표 API:
- `GET /api/contexts`
- `GET /api/contexts/{context_id}/tree`
- `GET /api/contexts/{context_id}/full-tree`

### 4) 변경 관리 (영향도 분석 → 변경 계획 → 적용)

유저스토리 변경이 야기하는 영향도를 분석하고, LLM 기반으로 변경 계획을 만들고, 승인된 계획을 Neo4j에 반영합니다.

대표 API:
- `GET /api/change/impact/{user_story_id}`
- `POST /api/change/plan`
- `POST /api/change/apply`

### 5) 모델 수정(Chat) (ReAct + Streaming)

대표 API:
- `POST /api/chat/modify`
- `GET /api/chat/node/{node_id}`

### 6) PRD/에이전트 컨텍스트 파일 생성

Neo4j 그래프를 기반으로 PRD 및 개발 에이전트 컨텍스트 파일들을 ZIP으로 생성합니다.

대표 API:
- `GET /api/prd/tech-stacks`
- `POST /api/prd/generate`
- `POST /api/prd/download`

---

## API 개요

API는 기능별로 prefix가 구분돼 있습니다.

- **Health**: `/api/health`
- **Ingestion**: `/api/ingest/...`
- **Contexts**: `/api/contexts/...`
- **Canvas Graph**: `/api/graph/...`
- **Change Management**: `/api/change/...`
- **User Story Authoring**: `/api/user-story/...`
- **User Story Catalog**: `/api/user-stories/...`
- **Chat Model Modifier**: `/api/chat/...`
- **PRD Generator**: `/api/prd/...`
- **ReadModel/CQRS**: `/api/readmodel/...`, `/api/cqrs/...`

정확한 요청/응답 스펙은 `http://localhost:8000/docs`를 참고하세요.

---

## 그래프(Neo4j) 스키마

기본 Event Storming 스키마(Cypher)는 아래 경로에 정리돼 있습니다.

- `docs/cypher/schema/01_constraints.cypher`
- `docs/cypher/schema/02_indexes.cypher`
- `docs/cypher/schema/03_node_types.cypher`
- `docs/cypher/schema/04_relationships.cypher`
- `docs/cypher/sample_data.cypher`

핵심 개념(요약):

- **Node**: `Requirement`, `UserStory`, `BoundedContext`, `Aggregate`, `Command`, `Event`, `Policy`, `Property`, `UI`
- **Relationship**: `IMPLEMENTS`, `HAS_AGGREGATE`, `HAS_COMMAND`, `EMITS`, `TRIGGERS`, `INVOKES`, `HAS_PROPERTY`, `HAS_UI`, `ATTACHED_TO`, ...

추가로, UI에서 ReadModel/CQRS 설정을 위한 `ReadModel`, `CQRSConfig`, `CQRSOperation`, `CQRSMapping`, `CQRSWhere` 등의 노드를 API가 생성/관리합니다. (세부는 Swagger 및 `api/features/readmodel_cqrs/` 참고)

---

## CLI (옵션)

일부 Event Storming 워크플로우는 터미널에서 실행할 수 있습니다.

```bash
uv run python -m api.features.ingestion.event_storming.cli status
uv run python -m api.features.ingestion.event_storming.cli add-story -r customer -a "cancel my order" -b "I can get a refund"
uv run python -m api.features.ingestion.event_storming.cli run
uv run python -m api.features.ingestion.event_storming.cli impact OrderCancelled
```

---

## 프로젝트 구조

```text
.
├── api/                          # FastAPI 백엔드 (Neo4j + LLM)
│   ├── main.py                   # API 엔트리포인트
│   ├── platform/                 # env/neo4j/observability 공통
│   └── features/                 # 비즈니스 기능별 라우터
├── frontend/                     # Vue/Vite 프론트엔드 (Canvas/Navigator UI)
├── docs/
│   ├── cypher/                   # 스키마/샘플데이터/쿼리
│   └── PRD*.md                   # 산출물 예시(참고용)
├── logs/                         # 실행 로그(JSONL 등)
├── pyproject.toml                # Python 의존성/툴 설정(uv 권장)
├── requirements.txt              # pip 대안 설치용
└── .env.example                  # .env 템플릿
```

---

## 라이선스

MIT License


