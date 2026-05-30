# Phase 0 Research: Epic / Feature 단위 요구사항 등록·뷰·편집·레이더 필터링

**Feature**: 034-requirement-epic-feature-units | **Date**: 2026-05-30

스펙의 Assumptions에서 두 핵심 스코프 결정(Epic = BoundedContext, AI 제안+수동 병행)은 사용자 확인으로 이미 해소됨. 본 문서는 구현 접근에 필요한 나머지 결정(D1–D7)을 기존 코드 사실에 근거해 정리한다. **잔여 NEEDS CLARIFICATION 없음.**

---

## D1 — Epic의 실체: 신규 노드 vs 기존 BoundedContext

**Decision**: Epic = 기존 `BoundedContext` 노드. 신규 라벨/관계 도입하지 않음.

**Rationale**: 현재 Requirements 트리는 이미 `BoundedContext(Epic) → Feature → UserStory`로 렌더된다(`RequirementsTree.vue`, `requirements_tree.py`). clarity radar의 `ScopeType` enum도 `bounded_context`를 지원한다. 새 Epic 노드를 만들면 Constitution I(단일 진실원)·II(어휘) 위반 위험과 트리·clarity 재배선 비용이 크다. 사용자도 "기존 BoundedContext = Epic"을 선택.

**Alternatives considered**: (a) 별도 Epic 노드 — 데이터 모델·관계·clarity scope·트리 전부 변경 필요, 기각. (b) Feature 묶음 라벨 — 물리 그룹이 없어 뷰/편집/스코프 대상이 모호, 기각.

---

## D2 — Feature/Epic 편집(rename) 라우트 부재 해소

**Decision**: 신규 직접-편집 라우트 2종 추가 — `PATCH /api/requirements/feature`(이름·설명 수정), `PATCH /api/requirements/bounded-context`(이름·설명 수정). Neo4j 쓰기는 기존 `features.py`/`bounded_contexts.py`에 `update_feature()`/`update_bounded_context()`를 추가해 처리(속성 SET, 관계 보존).

**Rationale**: 코드 조사 결과 Feature는 create/delete만 있고 **update가 없으며**, BoundedContext는 ingestion 경로로만 생성되고 UI 라우트가 전혀 없다(FR-010 충족 불가). 편집은 사용자의 직접 의도적 mutation이므로 Constitution IV(propose→apply는 LLM 생성 변경 대상)에 해당하지 않아 단발 PATCH로 충분하다. 기존 노드의 속성만 SET하고 `HAS_FEATURE`/`HAS_USER_STORY` 관계는 건드리지 않아 하위 연결 보존(FR-012).

**Alternatives considered**: change-plan/apply 2단계 — LLM 비관여 단순 rename에는 과설계, 기각.

---

## D3 — Epic 생성 라우트 부재 해소

**Decision**: 신규 `POST /api/requirements/bounded-context` 추가. 기존 `create_bounded_context()`(MERGE on `key`) 재사용. 입력은 name(+선택 description); `key`/`displayName`은 서버가 기존 규칙으로 도출.

**Rationale**: 사용자가 "+"로 Epic을 등록(FR-002)하려면 UI에서 호출 가능한 생성 라우트가 필요한데 현재 ingestion-only다. `create_bounded_context()`가 이미 존재하므로 라우트 래핑만으로 충족. `key` 충돌 시 MERGE 의미로 안전.

**Alternatives considered**: 트리 클라이언트가 ingestion 우회 — 어휘/계층 일관성 깨짐, 기각.

---

## D4 — Epic/Feature AI 제안(propose) 흐름

**Decision**: `POST /api/requirements/epic/propose`, `POST /api/requirements/feature/propose` 추가 — 자연어 입력 → LLM 후보 제시(미확정) → 사용자 확정 시 D3/기존 feature-create로 영속. 기존 user-story propose/confirm 패턴과 동일한 propose→confirm 분리.

**Rationale**: 사용자가 "AI 제안 + 수동 둘 다"를 선택(FR-005). Constitution IV에 따라 LLM 생성 후보는 반드시 확정 전 검토 가능해야 한다(FR-006). 기존 `user_story_crud.py`의 propose/confirm 구조와 provider-agnostic runtime(Constitution VI)을 그대로 재사용해 신규 LLM 패턴 도입을 피한다. 후보 0건/실패 시 수동 폼으로 폴백(FR-006).

**Alternatives considered**: 자동 적용(확인 없음) — Constitution IV 위반, 기각.

---

## D5 — clarification radar 범위 필터링 연동

**Decision**: 프런트만 배선. 트리/뷰에서 노드 선택 시 `store.fetchClarityScores(scopeType, scopeId)`를 호출 — Epic 선택 → `bounded_context`/bcId, Feature 선택 → `feature`/featureId, 선택 해제/전체 → `project`/`*`. 백엔드 변경 없음.

**Rationale**: `get_clarification_clarity()`와 `compute_clarity_scores_for_scope()`가 이미 `project|bounded_context|feature` scope를 지원하며 트리 순회로 user_story_ids를 해소한다(코드 조사 확인). 따라서 신규 가치는 **선택→scope 매핑→호출**의 프런트 배선과 빈 상태 처리(FR-015)에 한정된다.

**Alternatives considered**: 백엔드 신규 scope 엔드포인트 — 중복, 기각.

---

## D6 — "뷰 페이지/편집 페이지"의 구현 형태

**Decision**: URL 라우트가 아니라 Requirements 탭 내부의 전용 패널(Detail/Edit 컴포넌트). 선택 노드 타입에 따라 `RequirementsPanel`이 `EpicDetail`/`FeatureDetail`/`UserStoryDetail`(기존)로 분기하고, 각 Detail에서 "편집" 토글로 EditForm 표시.

**Rationale**: 현재 앱은 탭 기반 SPA로 vue-router 딥링크가 없다(코드 조사: `App.vue` activeTab, no route params). 기존 UserStoryDetail이 우측 패널 인라인으로 동작하므로 동일 패턴이 일관적이며 회귀 위험이 가장 낮다(FR-009, SC-006). 별도 라우트는 Out of Scope.

**Alternatives considered**: vue-router 도입 + `/requirements/epic/:id` — 탭 SPA 전반 재구조화 필요, 범위 초과, 기각.

---

## D7 — 편집 동시성/충돌 처리 수준

**Decision**: 낙관적 단순 처리 — 저장 시 대상 노드 존재 확인, 없으면 친절한 안내(삭제/외부 변경). 엄격한 버전 락/머지는 도입하지 않음.

**Rationale**: 스펙 Assumptions의 단일 사용자 로컬 신뢰 모델. Edge Case(외부 변경/삭제)는 정보성 안내로 충분하며, 락은 과설계.

**Alternatives considered**: 낙관적 버전 토큰(updatedAt 비교) — 후속 멀티유저 기능에서 도입 여지로 남김, 현 범위 기각.

---

## 재사용 인벤토리 (요약)

| 필요 | 기존 자산 | 신규 |
|------|-----------|------|
| 트리 조회 | `GET /tree` (`requirements_tree.py`) | — |
| User Story 등록 | `POST /user-story/propose`·`/confirm` | — (회귀 유지) |
| Feature 생성/삭제 | `POST`·`DELETE /feature` | — |
| Feature 편집 | — | `PATCH /feature` + `update_feature()` |
| Epic(BC) 생성 | `create_bounded_context()` (ops만) | `POST /bounded-context` 라우트 |
| Epic(BC) 편집 | — | `PATCH /bounded-context` + `update_bounded_context()` |
| Epic/Feature AI 제안 | user-story propose 패턴·LLM runtime | `POST /epic/propose`·`/feature/propose` |
| radar scope 집계 | `GET /clarification/clarity`(scope 지원), `compute_clarity_scores_for_scope` | — (프런트 배선만) |
| 뷰/편집 UI | `UserStoryDetail.vue`, `ClarityRadar.vue` | `EpicDetail/EpicEditForm/FeatureDetail/FeatureEditForm.vue` |

---

## D8 — 하위 US 자동 생성 엔진 이원화 (US5)

**Decision**: 생성 엔진을 Settings 토글 `requirementGenerationEngine: 'in-process' | 'claude-ide'`로 이원화.
- **in-process**: spec 008 `run_user_story_planning()`(`api/features/user_stories/planning_agent/`, LangGraph + `get_llm()`)을 Epic/Feature 컨텍스트로 호출해 하위 US 후보 생성. 신규 라우트 `POST /epic|feature/{id}/generate-stories`가 오케스트레이션, 결과는 **제안**으로 반환 → 사용자 확정 시 기존 US 영속 경로로 저장.
- **claude-ide**: 사용자 로컬 `claude` CLI를 통해 speckit-specify(또는 robo-spec 스킬)로 생성. spec 015/029의 `claude_code` 자산 재사용.

**Rationale**: 사용자가 "설정에서 in-process LLM 또는 claude ide 선택"을 명시(FR-020). 008 planning agent가 이미 in-process·HITL(add/apply) 구조라 재사용이 자연스럽다. Constitution VI(provider-agnostic)는 in-process 경로가 `get_llm()`으로 충족하고, claude-ide는 사용자 자신의 로컬 도구이므로 백엔드 provider 하드코딩이 아니다.

**Alternatives considered**: 단일 엔진 강제 — 사용자 요구(선택권)와 불일치, 기각. clarification 재사용 — clarification은 ambiguity scan이지 US 생성이 아님, 부적합.

---

## D9 — "Claude IDE" 엔진의 호출 메커니즘 + 설치 점검 (US5)

**Decision**: (1) **설치 preflight** — 엔진이 `claude-ide`일 때 `shutil.which("claude")` 및 speckit/robo-spec 스킬 존재를 점검(현재 코드엔 점검이 없음: `claude_code/router.py`는 exec 실패 시 shell로 폴백할 뿐). 미설치 시 생성 대신 **설치 안내**(FR-021). (2) **호출** — 로컬 `claude`를 헤드리스로 구동해 `/speckit-specify`(또는 robo-spec 검증/생성 스킬)를 실행하고, 스킬은 robo-spec **MCP(`/mcp`)** 로 그래프(BC/Feature/US)·기존 spec 컨텍스트를 읽고 결과를 제안으로 되돌린다. 기존 `_install_robo_spec()`(`claude_code/router.py:340`)이 repo `skills/robo-spec/` + speckit-{plan,tasks,implement}를 워크스페이스 `.claude/skills/`로 복사하는 패턴을 확장.

**Rationale**: 사용자가 "기존 .claude home에 설치된 speckit 그대로 이용 + 미설치 시 설치 유도"를 명시(FR-021). 현재 백엔드는 `claude`를 PTY 터미널로만 띄우고 설치 점검이 없으므로(Research 조사) preflight는 **신규 작업**이다. robo-spec MCP가 이미 그래프 접근 툴(resolve/get_bc_design/list_design_elements/propose/apply)을 제공하므로 스킬↔백엔드 데이터 경로는 재사용.

**Alternatives considered**: exec 실패에만 의존 — 사용자에게 "왜 안 되는지" 안내가 빈약, 기각. 백엔드가 claude를 완전 헤드리스 오케스트레이션 — Electron/로컬 환경 제약, 1차로는 워크스페이스+스킬 경로로 최소화.

---

## D10 — 장시간 생성의 진행 스트리밍 (Constitution III, US5/US7)

**Decision**: 하위 US 자동 생성과 설계 반영은 `sse_starlette.EventSourceResponse`로 단계/진행을 스트리밍하고 취소를 지원. `api/features/ingestion`의 `/api/ingest/stream/{session_id}` 패턴을 차용.

**Rationale**: 008 planning add와 004 change plan은 **현재 동기 응답**이라 Constitution III(2초+ 작업은 스트리밍)를 충족하지 못한다. Epic 단위 다건 US 생성·다건 설계 반영은 수십 초가 걸릴 수 있으므로 진행 표시·취소(FR-022)가 필요하다.

**Alternatives considered**: 동기 응답 유지 — 원칙 III 위반·UX 저하, 기각.

---

## D11 — DDD 적합성·입도·spec 정합성 검증 (US6)

**Decision**: 검증을 **스킬 기반**으로 제공. speckit 기본 스킬군에는 BC 배치/입도/spec 충돌 전용 검증이 없으므로(존재하는 `speckit-analyze`는 spec-kit 산출물 일관성용) **robo-spec 신규 스킬 `robo-validate`**(또는 `speckit-specify` override)를 추가한다. 스킬은 robo-spec **MCP**로 (a) 정의된 BC 목록·Feature/US 트리, (b) 기존 spec 컨텍스트를 읽어 — 잘못된 BC 배치, 과대 Feature 입도, 기존 spec 충돌을 진단하고 **교정안(재배치/분할/정합)** 을 제안. in-process 엔진에서는 동일 검증을 백엔드 에이전트(`POST /requirements/validate`)가 그래프+spec으로 수행. 교정안은 비차단(경고 후 강행 허용, 단 BC 부재 시 BC 선행).

**Rationale**: 사용자가 "speckit 스킬로 검증, 없으면 robo-spec에서 override/신규"를 명시(FR-027). robo-spec 스킬은 이미 `extends: speckit-*`로 override 가능함이 확인됨(`skills/robo-spec/robo-plan/SKILL.md`). MCP 툴(`get_bc_design`, `list_design_elements`)이 BC/설계 컨텍스트를 제공.

**Alternatives considered**: 순수 백엔드 규칙엔진 — DDD 판단은 맥락적이라 규칙화 어려움, LLM/스킬이 적합. 검증 생략 — 그래프 일관성 붕괴 위험, 기각.

---

## D12 — 미반영 US 식별 (US7)

**Decision**: "설계 미반영 US" = design-trace가 비어 있는 US. 판정은 `MATCH (us:UserStory)-[:IMPLEMENTS]->(:Command)` 부재로 한다(`design_trace.py`가 동일 관계를 사용, empty:true 반환). 신규 라우트 `GET /api/requirements/user-stories/pending-design`가 프로젝트/범위 내 미반영 US 목록을 반환.

**Rationale**: 기존 design-trace가 이미 `IMPLEMENTS→Command` 유무로 설계 반영 여부를 표현한다(Research 조사). 별도 플래그 도입 없이 기존 관계의 부재로 판정 → 신규 스키마 0건(FR-035).

**Alternatives considered**: US에 `designReflected` 속성 추가 — 중복 상태원·동기화 부담, 기각.

---

## D13 — 설계 자동 반영 오케스트레이션 (US7)

**Decision**: 탭 진입 훅(프런트 `_onSwitchTab`, `App.vue`의 'Event Modeling'→`EventModelingPanel`, 'Design'→`CanvasWorkspace`) → `pending-design` 조회 → 있으면 "설계에 반영하시겠습니까?" 프롬프트(`DesignReflectPrompt.vue`). 동의 시 신규 `POST /api/requirements/design/reflect`가 미반영 US별로 **기존 change_management `/api/change/plan`→`/apply`(propose→apply, HITL)** 를 오케스트레이션해 journey/Aggregate 생성·변경을 만들고, 사용자 확인 후 그래프 반영. 진행은 D10 SSE로 표시. "세션 내 다시 묻지 않기" 옵션 제공(FR-034).

**Rationale**: 사용자가 "탭 이동 시 미반영 US 자동 식별→질문→자동 설계, journey 추가·Aggregate 생성/변경"을 명시(FR-030~033). 설계 생성 엔진을 새로 만들지 않고 기존 change-plan/apply·Event Modeling을 트리거(Out of Scope: 설계 알고리즘 신규). change-plan은 이미 propose→apply라 HITL 충족.

**Alternatives considered**: 백그라운드 자동 반영(무프롬프트) — Constitution IV·사용자 의도("질문을 받은 후") 위반, 기각.

---

## D14 — 엔진 선택 설정의 저장 위치 (US5)

**Decision**: `requirementGenerationEngine`를 앱 Settings에 저장 — 프런트 `SettingsPanel.vue`(+Pinia) 노출, Electron은 `DesktopSettings`(`desktop/src/shared/ipc-contract.ts`, `main/settings.ts`)에 필드 추가 + 기본값 `'in-process'` 마이그레이션. **그래프에 저장하지 않음**(모델 상태가 아니라 도구 설정).

**Rationale**: 엔진 선택은 사용자/머신 환경 설정이지 도메인 모델이 아니므로 Constitution I(그래프=모델 진실원)와 무관하게 Settings가 옳다. 기존 Settings 자산 재사용.

**Alternatives considered**: 그래프 저장 — 원칙 오용, 기각. 하드코딩 — 선택 요구와 불일치, 기각.
