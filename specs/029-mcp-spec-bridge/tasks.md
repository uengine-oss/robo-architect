---
description: "Task list for MCP Spec Bridge implementation"
---

# Tasks: MCP Spec Bridge — 동적 스펙 전달과 구현 진척 동기화

**Input**: Design documents from `/specs/029-mcp-spec-bridge/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/mcp-and-rest.md

**Tests**: 포함 — plan.md가 `api/features/mcp_bridge/tests/`에 서비스/파서 단위 테스트를 명시했고, Playwright e2e 1건을 폴리시에 둔다.

**Organization**: 작업은 User Story(US1~US5) 단위로 묶어 각각 독립 구현·테스트 가능하게 한다.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 병렬 실행 가능(다른 파일, 미완료 의존 없음)
- **[Story]**: 해당 User Story 라벨
- 설명에 정확한 파일 경로 포함

## Path Conventions

Web application 미러 구조 — 백엔드 `api/features/mcp_bridge/`, 프런트 `frontend/src/features/requirements/`. 보조 stdio MCP 프로세스는 `api/features/mcp_bridge/server.py`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: 신규 feature 모듈 골격과 의존성·라우터 등록

- [X] T001 `api/features/mcp_bridge/` 패키지 골격 생성 — `__init__.py`, `routes/__init__.py`, `templates/`, `tests/__init__.py` 디렉터리/빈 파일
- [X] T002 [P] `mcp`(FastMCP)·`httpx` 의존성을 `pyproject.toml`과 `requirements.txt`에 추가
- [X] T003 `api/main.py`에 `mcp_bridge` 라우터 import + `app.include_router(mcp_bridge_router)` 등록(다른 feature 라우터 등록 패턴 준수)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: 모든 User Story가 의존하는 공통 인프라

**⚠️ CRITICAL**: 이 단계 완료 전 어떤 User Story도 시작 불가

- [X] T004 [P] `api/features/mcp_bridge/mcp_bridge_contracts.py`에 전체 Pydantic DTO 정의 — `ScopeRef`, `SpecBundleArtifact`, `SpecBundleResponse`, `ScopeNotFoundResponse`, `InstallCommandRequest/Response`, `TaskItemDTO`, `CodeLocationDTO`, `ScopeProgressDTO`, `ProgressResponse` (data-model.md §2)
- [X] T005 `api/features/mcp_bridge/router.py` 생성 — prefix `/api/mcp-bridge`, tags `["mcp-bridge"]`, `routes/`의 하위 라우터를 include하는 골격
- [X] T006 [P] `api/features/mcp_bridge/` 공용 관측성 헬퍼 — `mcp_bridge.*` 로그 카테고리 + correlation ID 부착(`api/platform/observability` SmartLogger 재사용, ddd_spec `GenerationContext` 패턴 참고)

**Checkpoint**: Foundation 준비 완료 — User Story 구현 시작 가능

---

## Phase 3: User Story 1 - 선택한 피처/BC/어그리거트로 구현 커맨드 생성 (Priority: P1) 🎯 MVP

**Goal**: 아키텍트가 범위를 선택해 "구현 커맨드 생성"을 실행하면 대상 프로젝트에 범용 슬래시 커맨드가 설치되고 `.mcp.json`에 MCP 서버가 등록되며 호출 문자열이 제시된다.

**Independent Test**: Requirements 탭에서 Feature를 선택해 커맨드 생성을 실행 → 대상 프로젝트 `.claude/commands/robo-implement.md` 설치·`.mcp.json` 등록·호출 문자열 제시 확인; 재실행 시 중복 누적 없음(멱등).

### Tests for User Story 1

- [X] T007 [P] [US1] `api/features/mcp_bridge/tests/test_command_installer.py` — 신규 설치, 멱등 재설치(중복 없음), 기존 `.mcp.json` 타 항목 보존, `projectHome` 무효 시 에러

### Implementation for User Story 1

- [X] T008 [P] [US1] `api/features/mcp_bridge/templates/robo-implement.md` 작성 — `$ARGUMENTS`=`<scopeType> <scopeId>`로 MCP 도구 `get_spec_bundle` 호출 → `.robo/tasks/<scopeType>-<scopeId>.md`(frontmatter+체크박스+`<!-- impl: -->` 규약, data-model §3.3) 작성 → 순차 구현·체크박스/impl 갱신 → 정적 스펙 `.md` 생성 금지 지시
- [X] T009 [US1] `api/features/mcp_bridge/command_installer.py` 구현 — `.claude/commands/robo-implement.md` 멱등 쓰기 + 프로젝트 루트 `.mcp.json`의 `mcpServers.robo-architect` 멱등 upsert(기존 항목 보존, research R7), `ROBO_API_BASE` env 주입
- [X] T010 [US1] `api/features/mcp_bridge/routes/install_command.py` 구현 — `POST /install-command`, `InstallCommandRequest` 처리, `projectHome` 디렉터리 검증(422), `InstallCommandResponse`(`invocation`·`commandInstalled`·`mcpRegistered`) 반환
- [X] T011 [P] [US1] `frontend/src/features/requirements/ui/GenerateCommandDialog.vue` 신규 — 범위 표시, 프로젝트 홈 미지정 가드(FR-004), 설치 결과·호출 문자열 복사 UI
- [X] T012 [US1] `frontend/src/features/requirements/requirements.store.js`에 install 액션 추가 + `RequirementsTree.vue`(및 Aggregate 탭)에 "구현 커맨드 생성" 진입점 연결

**Checkpoint**: User Story 1 독립 동작·테스트 가능

---

## Phase 4: User Story 2 - MCP가 PRD·구현 스펙을 동적으로 전달 (Priority: P1)

**Goal**: Claude Code에서 슬래시 커맨드 실행 시 MCP가 범위 ID로 Robo API를 호출해 호출 시점 최신 스펙을 전달하고, 정적 `.md`는 생성하지 않는다.

**Independent Test**: 알려진 Feature ID로 MCP 도구 호출 → 그 범위 PRD·DDD 스펙 반환; 호출 직전 모델 수정이 응답에 반영; 없는 ID는 "범위 없음"; API 다운 시 "연결 불가" 명확 보고.

### Tests for User Story 2

- [X] T013 [P] [US2] `api/features/mcp_bridge/tests/test_spec_bundle_service.py` — `feature`/`bounded_context`/`aggregate` 범위별 묶음 조립(research R3), `generatedAt` 갱신, 없는 ID `scope_not_found`

### Implementation for User Story 2

- [X] T014 [US2] `api/features/mcp_bridge/spec_bundle_service.py` 구현 — `ddd_spec` projection·repository·렌더러를 in-memory로 호출해 `SpecBundleResponse` 조립(디스크 쓰기 없음, FR-008); 범위 종류별 조립 규칙(R3); SVG 와이어프레임 생략
- [X] T015 [US2] `api/features/mcp_bridge/routes/spec_bundle.py` 구현 — `GET /spec-bundle?scopeType=&scopeId=`, 200 `SpecBundleResponse` / 404 `ScopeNotFoundResponse` / 422 잘못된 `scopeType`
- [X] T016 [US2] `api/features/mcp_bridge/server.py` 구현 — FastMCP stdio 서버, 도구 `get_spec_bundle(scope_type, scope_id)`가 `httpx`로 `{ROBO_API_BASE}/api/mcp-bridge/spec-bundle` 호출; 404→"범위 없음"(FR-010), 연결 실패→"API 연결 불가"(FR-011); 진단 로그는 stderr only

**Checkpoint**: User Story 1·2 각각 독립 동작

---

## Phase 5: User Story 3 - 구현 중 갱신되는 태스크 파일 (Priority: P2)

**Goal**: 슬래시 커맨드가 `.robo/tasks/<scopeType>-<scopeId>.md`를 SpecKit 체크박스 형식으로 펼치고 구현 진행에 따라 갱신한다. (태스크 파일 작성·갱신 동작은 T008 슬래시 커맨드 템플릿이 Claude Code에 지시한다 — 본 단계는 그 산출물을 기계 판독하는 파서를 제공한다.)

**Independent Test**: 슬래시 커맨드 실행 후 `.robo/tasks/`에 frontmatter+체크박스 태스크 파일 생성·진행 중 체크 갱신·완료 항목 `<!-- impl: -->` 부착 확인; 파서가 정상/부분손상 파일을 모두 처리.

### Tests for User Story 3

- [X] T017 [P] [US3] `api/features/mcp_bridge/tests/test_task_file.py` — frontmatter·체크박스(`- [ ]`/`- [x]`)·`<!-- impl: -->` 매핑 파싱, frontmatter 손상 시 파일명에서 범위 복구(FR-014), 부분손상 회복(FR-021)

### Implementation for User Story 3

- [X] T018 [US3] `api/features/mcp_bridge/task_file.py` 구현 — `.robo/tasks/*.md` 파서: YAML frontmatter, 태스크 ID/설명/체크 상태, `impl:` 주석 → `TaskItemDTO`/`CodeLocationDTO`; 손상 시 예외 대신 부분 결과+사유 반환

**Checkpoint**: User Story 1·2·3 각각 독립 동작

---

## Phase 6: User Story 4 - Robo Architect가 구현 진척을 가시화 (Priority: P2)

**Goal**: Requirements 탭이 `.robo/tasks/`를 폴링해 각 범위를 미착수·진행 중·구현 완료(체크박스 비율)로 표시한다.

**Independent Test**: 태스크 파일 체크박스를 일부/전부 체크 → 탭에서 해당 범위가 진행 중/구현 완료로 갱신; 디렉터리 없음·손상 파일에도 탭 비파괴.

### Tests for User Story 4

- [X] T019 [P] [US4] `api/features/mcp_bridge/tests/test_progress_service.py` — 체크박스 비율 상태 도출(0/일부/전부, data-model §4), `.robo/tasks/` 부재 시 빈 결과(FR-020), 손상 파일 시 해당 범위만 `parseError`·나머지 정상(FR-021)

### Implementation for User Story 4

- [X] T020 [US4] `api/features/mcp_bridge/progress_service.py` 구현 — `task_file.py`로 `.robo/tasks/*.md` 전부 파싱, `ScopeProgressDTO`(status·totalTasks·completedTasks·taskItems) 도출
- [X] T021 [US4] `api/features/mcp_bridge/routes/progress.py` 구현 — `GET /progress?projectHome=`, `ProgressResponse` 반환, 절대 5xx 미발생(FR-020/021)
- [X] T022 [US4] `frontend/src/features/requirements/requirements.store.js`에 5초 주기 `/progress` 폴링 추가 + `RequirementsTree.vue`에 노드별 진척 배지(미착수/진행중/구현완료·태스크 비율)

**Checkpoint**: User Story 1~4 각각 독립 동작

---

## Phase 7: User Story 5 - 요구사항·어그리거트에서 구현 코드로 점프 (Priority: P3)

**Goal**: 구현 완료 Feature/Aggregate에서 클릭으로 실제 소스 파일을 Claude Code IDE 워크스페이스 편집기에 연다.

**Independent Test**: 구현 완료 Aggregate에서 "코드로 점프" → 소스 파일이 편집기에 열림; 가리키던 파일 이동·삭제 시 "찾을 수 없음" 안내·탭 비파괴.

### Implementation for User Story 5

- [X] T023 [US5] `api/features/mcp_bridge/routes/code_location.py` 구현 — `GET /code-location?projectHome=&scopeType=&scopeId=`, 완료 태스크 `impl:` 매핑 집계, 각 경로 `exists` 표기(FR-025), 태스크 파일 없으면 빈 목록
- [X] T024 [US5] `frontend/src/features/requirements/ui/UserStoryDetail.vue`(및 Aggregate 탭)에 "코드로 점프" 액션 — `/code-location` 호출 → 존재 경로를 `GET /api/claude-code/file`로 열기(FR-024), 미존재 시 안내(FR-025); `requirements.store.js`에 액션 추가

**Checkpoint**: 모든 User Story 독립 동작

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: 여러 스토리에 걸친 마무리

- [X] T025 [P] `README.md` API 요약에 `/api/mcp-bridge` prefix(4 엔드포인트) 추가
- [X] T026 [P] `frontend/tests/`에 Playwright e2e 1건 — 커맨드 생성 → 진척 배지 → 코드 점프 골든 패스
- [X] T027 `specs/029-mcp-spec-bridge/quickstart.md` S1~S5 수동 스모크 검증 수행

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: 의존 없음 — 즉시 시작
- **Foundational (Phase 2)**: Setup 완료 후 — 모든 User Story를 차단
- **User Stories (Phase 3~7)**: Foundational 완료 후 시작
- **Polish (Phase 8)**: 대상 User Story 완료 후

### User Story Dependencies

- **US1 (P1)**: Foundational 후 시작 — 다른 스토리 의존 없음
- **US2 (P1)**: Foundational 후 시작 — 독립. (T016 MCP 서버는 T015 `/spec-bundle`를 런타임 호출하나 구현은 독립 가능)
- **US3 (P2)**: Foundational 후 시작 — T018 파서는 독립. 태스크 파일 작성 동작은 US1의 T008 템플릿이 제공
- **US4 (P2)**: T018(`task_file.py`) 완료에 의존 — progress_service가 파서를 사용
- **US5 (P3)**: T018(`task_file.py`) 완료에 의존 — code_location이 `impl:` 매핑을 사용

### Within Each User Story

- 테스트(요청됨) → 구현 순. 파서/서비스 → 라우트 → 프런트 순.
- US1: T008·T011 [P] → T009 → T010 → T012
- US2: T013 [P] → T014 → T015 → T016
- US4: T019 [P] → T020 → T021 → T022
- US5: T023 → T024

### Parallel Opportunities

- Setup: T002 [P]
- Foundational: T004·T006 [P] (T005는 라우트 골격이라 T004 후 권장)
- US1: T007·T008·T011 [P] (서로 다른 파일)
- US2: T013 [P]
- US3: T017 [P]
- US4: T019 [P]
- Polish: T025·T026 [P]
- Foundational 완료 후 US1·US2·US3는 병렬 진행 가능(US4·US5는 T018 대기)

---

## Parallel Example: User Story 1

```bash
# US1 시작 시 병렬 실행 가능:
Task: "test_command_installer.py 작성 — api/features/mcp_bridge/tests/test_command_installer.py"
Task: "슬래시 커맨드 템플릿 작성 — api/features/mcp_bridge/templates/robo-implement.md"
Task: "GenerateCommandDialog.vue 신규 — frontend/src/features/requirements/ui/GenerateCommandDialog.vue"
```

---

## Implementation Strategy

### MVP First (User Story 1 + 2)

1. Phase 1 Setup → Phase 2 Foundational 완료
2. Phase 3 US1(커맨드 생성) + Phase 4 US2(동적 스펙 전달) 완료 — 이 둘이 함께 "정적 파일 없이 최신 스펙으로 구현 시작"이라는 핵심 가치를 이룬다
3. **STOP & VALIDATE**: quickstart S1·S2로 독립 검증 → 데모 가능

### Incremental Delivery

1. Setup + Foundational → 기반 완성
2. US1 → 독립 테스트 → 데모
3. US2 → 독립 테스트 → 데모 (MVP — 동적 스펙 전달)
4. US3 → 태스크 파일 파서 → 데모
5. US4 → 진척 가시화 → 데모
6. US5 → 코드 점프 → 데모

### Parallel Team Strategy

Foundational 완료 후: 개발자 A=US1, B=US2, C=US3(T018) → C 완료 후 US4·US5 진행.

---

## Notes

- [P] = 다른 파일·미완료 의존 없음
- 각 User Story는 독립 완료·테스트 가능해야 함
- 테스트는 구현 전 실패 확인
- 신규 Neo4j 노드/관계 없음 — `docs/cypher/schema/` 변경 불필요
- 태스크 단위 또는 논리적 묶음마다 커밋
- MCP 서버(`server.py`) 변경 후에는 Claude Code 세션 재시작 필요(quickstart 런북)
