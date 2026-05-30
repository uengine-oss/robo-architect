# Implementation Plan: Epic/Feature 등록·뷰·편집, 하위 US 자동 생성, DDD 검증, 설계 자동 반영

**Branch**: `034-requirement-epic-feature-units` | **Date**: 2026-05-30 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/034-requirement-epic-feature-units/spec.md`

## Summary

Requirements 탭을 다섯 갈래로 확장한다: (1) "+"를 **Epic/Feature/User Story 3-granularity**로, (2) **Epic·Feature 전용 뷰/편집 패널**, (3) 선택 범위에 따른 **clarification radar 필터링**, (4) Epic·Feature 등록 시 **하위 US 자동 생성**(제안→확인; 엔진은 Settings에서 **in-process LLM** 또는 **로컬 Claude IDE+speckit** 선택, 후자는 미설치 시 설치 안내), (5) 추가·생성물의 **DDD 적합성·입도·기존 spec 정합성 검증**(speckit 스킬, 없으면 robo-spec 스킬이 speckit-specify override/신규), 그리고 (6) Event Modeling/Design 탭 진입 시 **미반영 US를 식별해 설계 자동 반영**(제안→확인, 기존 설계 파이프라인 재사용).

도메인 매핑은 기존 그래프 재사용: **Epic = `BoundedContext`, Feature = `Feature`, US = `UserStory`** — 신규 노드 라벨/관계 0건(Constitution I·II). 모든 LLM 산출물은 propose→confirm(Constitution IV)이며, 장시간 생성은 SSE로 진행 스트리밍(Constitution III).

**재사용 핵심**: in-process 생성은 spec 008 `run_user_story_planning()`(LangGraph+`get_llm()`), 설계 반영은 spec 004 change_management `/api/change/plan`·`/apply`(propose→apply), 미반영 US 판정은 design-trace(`UserStory-[:IMPLEMENTS]->Command` 부재), 로컬 Claude/skill 경로는 spec 015/029 `claude_code` PTY + `_install_robo_spec()` + robo-spec MCP(`/mcp`).

## Technical Context

**Language/Version**: Python 3.11+ (FastAPI), Vue 3 + Vite; Electron(desktop) main(TS)

**Primary Dependencies**: FastAPI, Neo4j 공식 드라이버, Pydantic; LangChain/LangGraph + provider-agnostic LLM runtime(`api/platform/llm.get_llm`); `sse_starlette`(진행 스트리밍); FastMCP(robo-spec `/mcp`); Vue 3 + Pinia; Electron `safeStorage`/settings.json

**Storage**: Neo4j 단일 진실원. 재사용 노드 `BoundedContext`/`Feature`/`UserStory`/`Command`/`Aggregate`/`Event` 및 관계 `HAS_FEATURE`·`HAS_USER_STORY`·`IMPLEMENTS`. **신규 라벨/관계 0건.** 엔진 선택값은 앱/Desktop Settings에 저장(그래프 아님 — 모델 상태 아님)

**Testing**: pytest(backend), Playwright(`frontend/tests/`)

**Target Platform**: 웹 SPA + Electron 데스크톱(탭 기반, URL 라우팅 없음). "Claude IDE" 엔진은 로컬 `claude` CLI 설치 전제

**Project Type**: Web application (feature-modular: `api/features/*` ↔ `frontend/src/features/*`)

**Performance Goals**: Epic/Feature 뷰 ≤2초(SC-003); 편집 즉시 반영(SC-004); 자동 생성/설계 반영은 SSE 진행 표시 + 취소(FR-022). radar 범위 전환 즉시

**Constraints**: 스키마 변경 0건; 기존 US add/detail/clarify·기존 설계 흐름 회귀 0건(SC-006); 단일 사용자 로컬 신뢰 모델; LLM 변경 전량 propose→confirm

**Scale/Scope**: 백엔드 신규 라우트 ~8(feature update, bc create/update, epic/feature propose, epic/feature→US expand, ddd-validate, pending-design, design-reflect 오케스트레이션) + 기존 ops/에이전트/MCP 확장; 프런트 신규 컴포넌트 ~7(단위 선택, EpicDetail/Edit, FeatureDetail/Edit, 생성 제안 리뷰, DDD 검증 결과, 설계반영 프롬프트) + Settings 토글; robo-spec 신규 검증 스킬 1; 7개 User Story

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Graph-as-Source-of-Truth (NON-NEGOTIABLE) | ✅ PASS | 등록/편집/자동생성/설계반영 산출물 전량 Neo4j ops로 영속(FR-029, FR-035). 엔진 선택값만 Settings(모델 상태 아님). 병렬 저장소 없음. |
| II. Event Storming Vocabulary | ✅ PASS | UI "Epic"=노드 `BoundedContext`, 라우트 `/bounded-context`. DDD 검증·설계는 BC/Aggregate/Command/Event 어휘 유지. |
| III. Streaming-First UX | ⚠️ GAP→해소 | 하위 US 자동생성(US5)·설계 반영(US7)은 장시간 LLM. **현 planning/change-plan은 동기 응답** → 본 기능에서 `sse_starlette` 패턴(`/api/ingest/stream` 참조)으로 **진행 스트리밍 추가**(FR-022). Research D10. |
| IV. Human-in-the-Loop on Mutations | ✅ PASS | Epic/Feature 제안, 자동생성 US, DDD 교정안, 설계 변경 전부 propose→confirm(FR-019/028/033). 수동 rename만 직접 PATCH(LLM 비관여). |
| V. Feature-Modular Architecture | ✅ PASS | requirements/user_stories/change_management/claude_code/robo_spec 각 feature 내 변경. 교차 의존은 플랫폼·그래프·MCP 경유. |
| VI. Provider-Agnostic LLM Runtime | ✅ PASS | in-process 엔진은 `get_llm()` 추상화. "Claude IDE" 엔진은 사용자 로컬 Claude(백엔드 provider 하드코딩 아님) — 설정 토글로 분리, Research D8. |
| VII. Observable by Default | ✅ PASS | 신규 라우트/에이전트는 correlation ID + 단계 로깅(SmartLogger). |
| VIII. Figma SceneGraph Pipeline (NON-NEGOTIABLE) | ➖ N/A | SceneGraph 생성 없음. |
| IX. Plugin ↔ Backend Dev-Loop | ➖ N/A | Figma 플러그인 비관여(단, "Claude IDE" 엔진은 spec 015/029 claude_code 런북 적용 — Research D9). |

**개발 워크플로 게이트**:
- **Graph Schema Changes**: 신규 노드 라벨/관계 0건 → `docs/cypher/schema/` 변경 불필요. ✅
- **API Documentation**: 신규 엔드포인트 `/docs` Swagger 노출. ✅
- **Frontend ↔ Backend Mirror**: 동일 PR에서 `frontend/src/features/requirements/`(+Settings, +robo-spec 스킬) 미러. ✅

**Gate 결과: PASS** — Principle III는 위반이 아니라 **본 기능이 충족해야 할 작업 항목**(SSE 추가)으로 plan에 반영. 정당화 필요한 위반 없음 → Complexity Tracking 불필요.

## Project Structure

### Documentation (this feature)

```text
specs/034-requirement-epic-feature-units/
├── plan.md · research.md · data-model.md · quickstart.md
├── contracts/
│   ├── requirements-epic-feature-contract.md      # US1–4 (등록/뷰/편집/radar)
│   ├── generation-validation-contract.md          # US5–6 (자동생성 엔진/설치점검/DDD검증 스킬)
│   └── design-reflect-contract.md                 # US7 (미반영 US 식별/설계 반영)
├── checklists/requirements.md
└── tasks.md   # /speckit-tasks (NOT here)
```

### Source Code (repository root)

```text
api/features/requirements/
├── requirements_contracts.py          # [EXTEND] Feature/BC update, Epic/Feature propose, Expand, DDD-validate, PendingDesign 모델
├── router.py                          # [EXTEND] 신규 서브라우트 등록
└── routes/
    ├── feature_crud.py                # [EXTEND] PATCH /feature
    ├── bounded_context_crud.py        # [NEW] POST·PATCH /bounded-context
    ├── epic_feature_propose.py        # [NEW] POST /epic|feature/propose
    ├── child_story_generation.py      # [NEW] POST /epic|feature/{id}/generate-stories (SSE) + confirm
    ├── ddd_validation.py              # [NEW] POST /requirements/validate (BC배치·입도·spec충돌)
    ├── design_reflect.py             # [NEW] GET /user-stories/pending-design, POST /design/reflect (오케스트레이션)
    ├── design_trace.py                # [REUSE] IMPLEMENTS→Command 부재 = 미반영 판정
    └── clarification.py               # [REUSE] clarity radar scope

api/features/user_stories/planning_agent/      # [REUSE] run_user_story_planning() (in-process, get_llm) — Epic/Feature→US 확장에 호출
api/features/change_management/routes/         # [REUSE] /api/change/plan·/apply (설계 변경 propose→apply)
api/features/ingestion/event_storming/neo4j_ops/{bounded_contexts,features}.py  # [EXTEND] update_*, 라우트에서 호출
api/features/claude_code/router.py             # [EXTEND] claude/speckit 설치 점검(preflight) + 헤드리스 호출 경로(US5 Claude IDE)
api/features/robo_spec/{mcp_server.py,router.py}  # [EXTEND] DDD 검증용 MCP 툴(BC/Feature/US/spec 컨텍스트 노출)
skills/robo-spec/robo-validate/SKILL.md        # [NEW] speckit-specify override/신규 — DDD·정합성 검증 스킬

frontend/src/features/requirements/
├── requirements.store.js              # [EXTEND] create/propose/update Epic·Feature, generateChildStories(SSE), validate, pendingDesign, reflectDesign, selectNode
└── ui/
    ├── AddRequirementDialog.vue        # [EXTEND] 단위 선택 + AI/수동
    ├── RequirementsPanel.vue           # [EXTEND] node-type 분기 + radar scope
    ├── EpicDetail/EpicEditForm/FeatureDetail/FeatureEditForm.vue   # [NEW]
    ├── GeneratedStoriesReview.vue      # [NEW] 자동생성 US 제안 리뷰(선택/수정/확정, 진행/취소)
    ├── ValidationFindings.vue          # [NEW] DDD 검증 결과·교정안
    └── ClarityRadar.vue                # [REUSE]
frontend/src/features/event_modeling/ 및 design(Canvas)
    └── [EXTEND] 탭 진입(_onSwitchTab) 훅 → 미반영 US 감지 → DesignReflectPrompt.vue [NEW]
frontend/src/app/layout/SettingsPanel.vue       # [EXTEND] requirementGenerationEngine 토글
desktop/src/shared/ipc-contract.ts + main/settings.ts  # [EXTEND] DesktopSettings.requirementGenerationEngine (+migration)

frontend/tests/requirement-epic-feature.spec.ts # [NEW] e2e (US1–7)
```

**Structure Decision**: feature-modular 레이아웃 유지(Constitution V). 신규 LLM 작업은 **기존 in-process 에이전트(008)·변경계획(004)을 재사용**하고 그 위에 (a) Epic/Feature→US 확장 오케스트레이션, (b) DDD 검증, (c) 미반영 US 식별·설계 반영 오케스트레이션을 얇게 추가한다. "Claude IDE" 엔진은 spec 015/029의 `claude_code`(PTY/스킬 설치)·`robo_spec`(MCP) 자산을 재사용하고, DDD 검증 스킬은 robo-spec 스킬셋에 추가(speckit-specify override 또는 신규 `robo-validate`). URL 라우팅 없는 탭 SPA이므로 "뷰/편집 페이지"는 패널로 구현.

## Complexity Tracking

> Constitution Check 위반 없음 — 작성 불필요. (Principle III SSE 보강은 위반이 아닌 정상 작업 항목.)
