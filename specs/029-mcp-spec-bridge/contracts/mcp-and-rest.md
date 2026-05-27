# Phase 1 Contracts: MCP Spec Bridge

생성: 2026-05-19 · Plan: [plan.md](plan.md) · Data Model: [data-model.md](data-model.md)

## A. MCP 인터페이스 (stdio 서버 — `api/features/mcp_bridge/server.py`)

서버명: `robo-architect` · 트랜스포트: stdio · `.mcp.json`으로 Claude Code가 기동.

### A.1 도구 `get_spec_bundle`

| 항목 | 값 |
|------|-----|
| 인자 | `scope_type: str` (`feature`/`bounded_context`/`aggregate`), `scope_id: str` |
| 동작 | `httpx`로 `GET {ROBO_API_BASE}/api/mcp-bridge/spec-bundle?scopeType=&scopeId=` 호출 |
| 성공 반환 | `SpecBundleResponse`(data-model §2.3) — 호출 시점 모델의 PRD·DDD 구현 스펙 |
| 범위 없음 | API 404 수신 → 도구는 "범위 {type}:{id} 를 찾을 수 없음"을 명확히 반환, 빈/오래된 스펙 금지(FR-010) |
| API 불가 | 연결 실패 → 도구는 "Robo Architect API에 연결할 수 없음({base})"을 명확히 반환, 추측 구현 유도 금지(FR-011) |

도구는 그래프에 대해 **읽기 전용**이며 어떤 mutation도 하지 않는다.

### A.2 환경 변수

| 변수 | 기본 | 용도 |
|------|------|------|
| `ROBO_API_BASE` | `http://127.0.0.1:8000` | Robo Architect API 베이스 — `.mcp.json` env로 주입 |

## B. REST 인터페이스 (라우터 prefix `/api/mcp-bridge`)

모든 응답은 Pydantic 모델, Swagger `/docs` 노출.

### B.1 `GET /api/mcp-bridge/spec-bundle`

동적 스펙 묶음 조회 — MCP 도구가 호출.

| 항목 | 값 |
|------|-----|
| 쿼리 | `scopeType` (필수), `scopeId` (필수) |
| 200 | `SpecBundleResponse` — `generatedAt`은 매 호출 갱신(캐시 금지, SC-003) |
| 404 | `ScopeNotFoundResponse` — `scopeId`가 그래프에 없음(FR-010) |
| 422 | `scopeType`이 허용 값 외 |

조립 규칙(R3): `bounded_context`=domain-terms+bc-canvas+aggregate-spec×N+requirements; `feature`=부모 BC domain-terms+bc-canvas+Feature 슬라이스 requirements+관련 aggregate-spec; `aggregate`=aggregate-spec+BC domain-terms. 정적 `.md` 파일을 디스크에 쓰지 않는다(FR-008).

### B.2 `POST /api/mcp-bridge/install-command`

대상 프로젝트에 범용 슬래시 커맨드 설치 + `.mcp.json` 등록.

| 항목 | 값 |
|------|-----|
| 바디 | `InstallCommandRequest`(data-model §2.5) |
| 200 | `InstallCommandResponse` — `commandPath`·`mcpJsonPath`·`invocation`·`commandInstalled`·`mcpRegistered` |
| 422 | `projectHome`이 존재하지 않는 디렉터리 |

`.claude/commands/robo-implement.md`와 `.mcp.json`의 `mcpServers.robo-architect` 항목을 멱등 처리한다 — 재호출 시 중복 누적 없음(FR-005). `.mcp.json`의 기존 타 항목은 보존(R7).

### B.3 `GET /api/mcp-bridge/progress`

대상 프로젝트의 `.robo/tasks/`를 폴링해 구현 진척 반환 — Requirements 탭이 5초 주기 호출.

| 항목 | 값 |
|------|-----|
| 쿼리 | `projectHome` (필수) |
| 200 | `ProgressResponse`(data-model §2.10) — `.robo/tasks/*.md` 전부 파싱 |
| 디렉터리 없음 | 200 + `tasksDirExists=false`, `scopes=[]`(전 범위 미착수 취급, FR-020) |
| 손상 파일 | 200 — 해당 `ScopeProgressDTO.parseError`만 채우고 나머지는 정상 반영(FR-021) |

`status`는 체크박스 비율로 도출(data-model §4). 엔드포인트는 절대 5xx로 탭을 깨뜨리지 않는다(FR-020/021, SC-006).

### B.4 `GET /api/mcp-bridge/code-location`

구현 완료 범위의 소스 위치 조회 — 코드 점프.

| 항목 | 값 |
|------|-----|
| 쿼리 | `projectHome` (필수), `scopeType` (필수), `scopeId` (필수) |
| 200 | `{ "scopeType", "scopeId", "locations": list[CodeLocationDTO] }` — 완료 태스크 `impl:` 매핑 집계 |
| 태스크 파일 없음 | 200 + `locations=[]` |

각 `CodeLocationDTO.exists`로 현재 디스크 존재 여부 표기 — 프런트는 미존재 시 "대상 코드를 찾을 수 없음"을 안내(FR-025). 프런트는 존재하는 경로를 기존 `GET /api/claude-code/file`로 열어 IDE 워크스페이스 편집기에 표시(FR-024).

## C. 프런트엔드 동작 계약 (Requirements 탭 — `frontend/src/features/requirements/`)

| 동작 | 계약 |
|------|------|
| 구현 커맨드 생성 | 트리/Aggregate 탭에서 범위 선택 → `GenerateCommandDialog` → `POST /install-command` → 응답의 `invocation` 복사 제공. 프로젝트 홈 미지정 시 먼저 지정 요구(FR-004) |
| 진척 배지 | 탭이 열린 동안 5초 주기 `GET /progress` → 트리 노드에 미착수/진행중/구현완료 배지 + 태스크 비율(FR-018/019) |
| 코드 점프 | 구현 완료 Feature/Aggregate에서 "코드로 점프" → `GET /code-location` → 존재하는 경로를 `GET /api/claude-code/file`로 열기(FR-023/024); 미존재 안내(FR-025) |

## D. 관측성 계약

`mcp_bridge.*` 로그 카테고리 — 페이즈 경계(spec-bundle 조회 시작/완료, install 시작/완료, progress 폴링, code-location 조회)에 correlation ID 부착(constitution VII). MCP 서버는 stdout을 MCP 프로토콜에 양보하고 진단 로그는 stderr로만 출력한다.
