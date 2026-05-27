# Phase 1 Data Model: MCP Spec Bridge

생성: 2026-05-19 · Plan: [plan.md](plan.md) · Research: [research.md](research.md)

본 기능은 **신규 Neo4j 노드 라벨·관계 타입을 도입하지 않는다.** 범위는 기존 그래프 노드를 참조하고, 진척은 파일 기반이다. 아래는 (1) 참조하는 기존 그래프 엔티티, (2) 신규 전송 DTO, (3) 파일 산출물 스키마다.

## 1. 참조하는 기존 그래프 엔티티 (변경 없음)

| 엔티티 | 라벨 | 용도 |
|--------|------|------|
| Bounded Context | `BoundedContext` | 범위 종류 `bounded_context`의 대상; spec-bundle 투영 단위 |
| Feature | `Feature` (spec 026 도입) | 범위 종류 `feature`의 대상; 소속 User Story 집합 |
| Aggregate | `Aggregate` | 범위 종류 `aggregate`의 대상 |
| User Story | `UserStory` | Feature 범위 묶음의 requirements 슬라이스 구성 |
| Command / Event / Policy | `Command` 등 | aggregate-spec·설계 괘적 투영에 사용(기존 `ddd_spec` 경로) |

범위 ID는 위 노드의 기존 식별자를 그대로 쓴다. spec-bundle 조립은 `ddd_spec`의 projection·repository 계층을 재사용한다.

## 2. 신규 전송 DTO (Pydantic — `mcp_bridge_contracts.py`)

### 2.1 ScopeRef

| 필드 | 타입 | 비고 |
|------|------|------|
| `scopeType` | `Literal["feature","bounded_context","aggregate"]` | 범위 종류 |
| `scopeId` | `str` | 기존 그래프 노드 ID |

### 2.2 SpecBundleArtifact

| 필드 | 타입 | 비고 |
|------|------|------|
| `kind` | `Literal["domain-terms","bc-canvas","aggregate-spec","requirements","prd"]` | 산출물 종류 |
| `title` | `str` | 사람용 제목 |
| `markdown` | `str` | in-memory 마크다운 본문(디스크 미기록) |

### 2.3 SpecBundleResponse — `GET /spec-bundle` 응답 / MCP 도구 반환

| 필드 | 타입 | 비고 |
|------|------|------|
| `scopeType` | `str` | 요청 범위 종류 |
| `scopeId` | `str` | 요청 범위 ID |
| `scopeName` | `str` | 범위 표시명 |
| `generatedAt` | `str` (ISO-8601) | 투영 시각 — 호출 시점 모델 반영 증거 |
| `artifacts` | `list[SpecBundleArtifact]` | 범위 종류별 산출물(R3 조립 규칙) |
| `warnings` | `list[GenerationWarning]` | 투영 경고(빈 BC 등) |

`code`/`message`를 갖는 `GenerationWarning`은 기존 `requirements_contracts` 정의를 재사용한다.

### 2.4 ScopeNotFoundResponse — 범위 없음(HTTP 404)

| 필드 | 타입 | 비고 |
|------|------|------|
| `code` | `Literal["scope_not_found"]` | |
| `message` | `str` | "범위 {scopeType}:{scopeId} 를 찾을 수 없음" |

MCP 도구는 이 응답을 받으면 빈/오래된 스펙을 반환하지 않고 "범위 없음"을 명확히 전달한다(FR-010).

### 2.5 InstallCommandRequest — `POST /install-command` 요청

| 필드 | 타입 | 비고 |
|------|------|------|
| `projectHome` | `str` | 대상 프로젝트 홈 절대경로 |
| `scopeType` | `str` | 선택 범위 종류(호출 문자열 생성용) |
| `scopeId` | `str` | 선택 범위 ID |
| `roboApiBase` | `str` (기본 `http://127.0.0.1:8000`) | MCP 서버에 주입할 API 베이스 |

### 2.6 InstallCommandResponse

| 필드 | 타입 | 비고 |
|------|------|------|
| `commandPath` | `str` | 설치된 `.claude/commands/robo-implement.md` 경로 |
| `mcpJsonPath` | `str` | 갱신된 `.mcp.json` 경로 |
| `invocation` | `str` | 아키텍트가 복사할 호출 문자열 — `/robo-implement <scopeType> <scopeId>` |
| `commandInstalled` | `bool` | 신규 설치 여부(false면 기존 재사용) |
| `mcpRegistered` | `bool` | `.mcp.json` 항목 신규 여부(false면 기존 유지) |

### 2.7 TaskItemDTO

| 필드 | 타입 | 비고 |
|------|------|------|
| `id` | `str` | 태스크 ID(예: `T001`) |
| `description` | `str` | 태스크 설명 |
| `done` | `bool` | 체크박스 상태 |
| `implLocations` | `list[CodeLocationDTO]` | 완료 태스크의 `impl:` 매핑(미완료면 빈 목록) |

### 2.8 CodeLocationDTO

| 필드 | 타입 | 비고 |
|------|------|------|
| `filePath` | `str` | 프로젝트 홈 기준 상대경로 |
| `symbol` | `str | None` | 함수/클래스 등 심볼(있으면) |
| `exists` | `bool` | 현재 디스크 존재 여부(코드 점프 가드, FR-025) |

### 2.9 ScopeProgressDTO — `GET /progress` 응답 요소

| 필드 | 타입 | 비고 |
|------|------|------|
| `scopeType` | `str` | |
| `scopeId` | `str` | |
| `scopeName` | `str` | 태스크 파일 frontmatter에서 |
| `status` | `Literal["not_started","in_progress","completed"]` | 체크박스 비율 도출(아래 §4) |
| `totalTasks` | `int` | |
| `completedTasks` | `int` | |
| `taskItems` | `list[TaskItemDTO]` | |
| `taskFilePath` | `str` | `.robo/tasks/...` 경로 |
| `parseError` | `str | None` | 손상 파일이면 사유(부분 파싱 결과는 그대로 채움, FR-021) |

### 2.10 ProgressResponse — `GET /progress` 응답

| 필드 | 타입 | 비고 |
|------|------|------|
| `projectHome` | `str` | |
| `scopes` | `list[ScopeProgressDTO]` | `.robo/tasks/` 내 모든 태스크 파일 |
| `tasksDirExists` | `bool` | 디렉터리 부재 시 false(전 범위 미착수 취급, FR-020) |

## 3. 파일 산출물 스키마 (대상 프로젝트 — Neo4j 외부)

### 3.1 슬래시 커맨드 — `.claude/commands/robo-implement.md`

범용 커맨드(범위당 누적 없음). `$ARGUMENTS`로 `<scopeType> <scopeId>`를 받아 MCP 도구 호출 → 태스크 파일 작성 → 구현 → 체크박스/`impl:` 갱신을 지시. 프로젝트당 1개, 멱등 덮어쓰기.

### 3.2 MCP 등록 — `.mcp.json` (프로젝트 루트)

`mcpServers.robo-architect` 항목을 멱등 upsert(R7). 기존 다른 항목·키 보존.

### 3.3 태스크 파일 — `.robo/tasks/<scopeType>-<scopeId>.md`

YAML frontmatter + SpecKit `tasks.md` 체크박스 본문(R5):

- frontmatter 키: `scopeType`, `scopeId`, `scopeName`, `generatedAt`, `roboApiBase`
- 태스크 줄: `- [ ] <id> <description>` / 완료 시 `- [x] <id> <description> <!-- impl: <relPath>[#symbol][, …] -->`
- 파서 `task_file.py`는 frontmatter·체크박스·`impl:` 주석을 추출하며, frontmatter 일부 손상 시 파일 경로(`<scopeType>-<scopeId>.md`)에서 범위를 복구한다.

## 4. 상태 전이 — 범위 구현 상태

태스크 파일 체크박스 비율로 도출(파생 값 — 저장하지 않음):

| 조건 | `status` |
|------|----------|
| 태스크 파일 없음 / `.robo/tasks/` 없음 | `not_started` |
| 태스크 0개 체크 | `not_started` |
| 1개 이상 체크, 전부는 아님 | `in_progress` |
| 모든 태스크 체크 | `completed` |

Feature/BoundedContext 노드의 표시 상태는 해당 범위 태스크 파일의 비율로 직접 도출하며, 트리 상위 노드는 하위 범위들의 진척을 집계해 표시할 수 있다(구현 시 단순 합산: 하위 completedTasks/totalTasks 합).

## 5. 검증 규칙

- `scopeType`은 세 값 중 하나만 허용 — 그 외 422.
- `scopeId`가 그래프에 없으면 spec-bundle은 404 `scope_not_found`(FR-010).
- `projectHome`은 존재하는 디렉터리여야 함 — 아니면 422.
- `install-command`는 `.claude/commands/`·`.mcp.json` 쓰기 전 `projectHome` 유효성 확인(FR-004는 프런트에서 프로젝트 홈 미지정 가드).
- 태스크 파일 파싱 실패 시 전체 `/progress`를 실패시키지 않고 해당 `ScopeProgressDTO.parseError`에만 기록(FR-021).
- `code-location`의 각 경로는 `exists`로 현재 존재 여부를 표기(FR-025).
