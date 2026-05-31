# Implementation Plan: DDD 발견 마법사 & 도메인 캔버스

**Branch**: `035-ddd-discovery-canvases` (현재 작업 트리: `main`) | **Date**: 2026-05-31 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/035-ddd-discovery-canvases/spec.md`

## Summary

`ddd-starter`(ddd-crew 8단계 프로세스) 스킬을 robo-architect에 통합한다. 핵심 4축:

1. **DDD 발견 마법사** — 요구사항 탭의 "맨땅 시작" + "에픽 추가" 양쪽에서 프로파일링→옵트인 단계(Understand→Discover→Decompose→Strategize→…→Code)를 진행. 기존 spec 030 `clarification_agent` 세션·SSE·answer→encode→apply 패턴과 spec 034 이원화 생성 엔진(in-process LLM vs `claude-ide`)을 그대로 재사용.
2. **피보탈 이벤트 기반 도출** — EventStorming에서 피보탈/핫스팟을 표시하고 피보탈 이벤트 경계로 서브도메인→BC를 도출. 기존 `Event` 노드에 `pivotal`/`hotspot` **속성 추가**(신규 라벨 0).
3. **Bounded Context Canvas + BC 상세 화면** — 현재 부재인 BC 상세를 요구사항 탭 `EpicDetail`의 탭(+캔버스)으로 추가하고, 설계 캔버스에서 BC 클릭 시 동일 상세를 연다. 자동생성은 기존 `ddd_spec` `BoundedContextProjection`/`bc_canvas` 렌더러·`POST /api/ddd-spec/generate-bounded-context` 재사용.
4. **Aggregate Design Canvas** — `AggregateViewerInspector`에 캔버스 탭 추가. `AggregateProjection`·`aggregate_spec` 렌더러·spec 027 불변조건 재사용.

**진실의 원천은 그래프**(Constitution I). 캔버스는 그래프 노드의 투영 뷰, `.ddd/` 마크다운은 그래프에서 생성하는 보조 내보내기다. 모든 LLM 변경은 propose→confirm(Constitution IV), 장기 작업은 SSE(Constitution III).

## 기존 Ingestion 파이프라인과의 통합 (정의)

### 현행 구조(조사 결과)

- **일괄 ingestion**은 별도 탭이 아니라 **Requirements 탭의 "문서 업로드" 모달**(`frontend/.../requirementsIngestion/ui/RequirementsIngestionModal.vue`, 진입: `RequirementsPanel.vue` "문서 업로드")이다. `POST /api/ingest/upload` → `GET /api/ingest/stream/{session_id}`(SSE) → `ingestion_workflow_runner`의 14단계(문서 파싱→US 추출→이벤트→BC 군집→Feature 그룹→Aggregate→Command→ReadModel→Policy→GWT→Invariant→UI…).
- 이벤트 도출은 **커맨드 중심·US 기반**(`events_from_user_stories.py`, `commands.py`의 EMITS). **빅픽처/피보탈/핫스팟 개념 없음.**
- ⚠️ **전체 일괄 ingestion은 시작 시 이벤트스토밍 라벨을 clear 후 재구축**(`ingestion_workflow_runner` 초기 단계). 단, **증분 설계 실행기**(`POST /api/ingest/user-stories/design` → `workflow/incremental_design_runner.py`)는 clear 없이 선택 US 범위만 설계(Events→Aggregates→Commands→ReadModels)하며 MERGE로 보존.
- **spec 034 design_reflect**: Event Modeling/Design 탭 진입 시 미반영 US 감지 → `DesignReflectPrompt` → 동일 `RequirementsIngestionModal`을 `attachSessionId`로 재사용해 증분 설계 스트림.
- **`ddd_spec`**: ingestion 파이프라인 밖의 **후행 투영/렌더러**(BC canvas·aggregate spec·context map). 마법사가 아닌 ingestion 결과에도 동일 적용.

### 통합 결정(사용자 확정)

1. **병행 + 상호 진입구 (FR-024).** 마법사와 "문서 업로드"는 Requirements 탭에 공존하고 같은 그래프를 공유한다. 일괄 모달 ↔ 마법사 교차 링크. 마법사는 **새 탭이 아니라 Requirements 탭의 진입구**(조사의 "Option A 새 탭" 권고는 본 결정으로 기각).
2. **이벤트 도출은 보완 (FR-026).** 커맨드 중심 도출 유지 + 마법사가 빅픽처/피보탈/핫스팟 계층 추가. 피보탈 경계가 BC 군집(현재 `bounded_contexts.py`가 LLM 추정)을 **사용자 확정 정보로 보강**. 중복 이벤트는 병합 후보.
3. **마법사 후반 단계 = 기존 설계 기계 오케스트레이션 (FR-025).** Decompose 확정→`bounded_context_crud` `POST /bounded-context`; Code/설계→`POST /api/ingest/user-stories/design`(`incremental_design_runner`); 마무리→`design_reflect`. **신규 생성기 없음.** `ddd_wizard_engine`은 단계 진행·HITL·SSE만 담당하고 실제 그래프 쓰기는 위 기존 경로 호출.
4. **clear 충돌 회피 (FR-027).** 마법사는 **clear 하는 전체 ingestion을 트리거하지 않는다**. 모든 확정은 비-clear 증분 경로(BC 생성·증분 설계·속성 PATCH)로 반영. 사용자가 마법사 이후 "문서 업로드"(전체)를 실행하면 사전 경고 + `Event.pivotal/hotspot`·확정 BC를 ingestion 보존 라벨/속성 carry-over에 포함(research D14).

### 통합 시밍(seam) 요약

| 마법사 단계 | 재사용 기존 경로 | 비고 |
|---|---|---|
| Discover(이벤트/피보탈) | 신규 `pivotal_events.py` + 기존 Event 노드 | `pivotal`/`hotspot` 속성 추가, 기존 도출과 dedup |
| Decompose(서브도메인→BC) | `POST /bounded-context`(`bounded_context_crud`) | 피보탈 경계로 후보 산출 후 확정 |
| Strategize(분류) | `contexts/classification`(generic 확장) | — |
| Define(BC Canvas) | `ddd_spec` `generate-bounded-context`·`bc_canvas` | 캔버스=투영, 편집 PATCH |
| Code(Aggregate/설계) | `/api/ingest/user-stories/design`(`incremental_design_runner`) | clear 없이 증분, MERGE |
| 마무리(미반영 반영) | spec 034 `design_reflect` + change apply | HITL |
| 내보내기 | `ddd_spec` 렌더러(경로 `.ddd/`로 매개변수화) | 보조 산출물 |

## Technical Context

**Language/Version**: Python 3.11+ (백엔드), Vue 3 + Vite (프런트엔드)

**Primary Dependencies**: FastAPI, `sse_starlette` (EventSourceResponse), LangChain/LangGraph + `get_llm` 런타임, Neo4j 공식 드라이버, Jinja2(캔버스 렌더러), Vue Flow, EventSource. 로컬 엔진 경로: `claude_code` PTY + `robo_spec` MCP + 사용자 로컬 `ddd-starter` 스킬.

**Storage**: Neo4j (진실의 원천). 마법사 세션 = in-process 휘발성 dict(030 `clarification_session` 패턴). `.ddd/`·`specs/bounded-contexts/` 마크다운 = 그래프 투영 내보내기. 엔진 설정 = 프런트 Pinia + Electron `DesktopSettings`.

**Testing**: pytest (백엔드 contract/integration), 기존 `clarification_agent/tests/` 패턴; 프런트는 수동 quickstart + 기존 회귀.

**Target Platform**: 로컬 데스크톱(Electron) + 브라우저, FastAPI 서버.

**Project Type**: Web application (feature-modular: `api/features/*` ↔ `frontend/src/features/*`).

**Performance Goals**: BC 상세/캔버스 오픈 < 3s(SC-003); 마법사 단계 진행은 SSE로 점진 표시(체감 지연 최소화).

**Constraints**: 신규 Neo4j 노드 라벨/관계 0건(속성 추가만); 모든 그래프 변경 propose→confirm; 생성 산출물 언어 = 기어 아이콘 설정(spec 031); provider-agnostic LLM(`get_llm`).

**Scale/Scope**: 7개 User Story(P1×3, P2×3, P3×1). 백엔드 신규 `generation/` 엔진 + `ddd_wizard/` 세션 + 라우트 묶음; 프런트 신규 마법사 패널 + BC 상세 탭 + 2개 캔버스 탭.

## Constitution Check

*GATE: Phase 0 이전 통과 필수, Phase 1 이후 재확인.*

| 원칙 | 평가 | 근거 |
|---|---|---|
| **I. Graph-as-Source-of-Truth** (NON-NEGOTIABLE) | ✅ PASS | 캔버스=그래프 투영, `.ddd`=재생성 가능한 내보내기. 병렬 model 저장소 없음(세션은 휘발성 in-process로 030과 동일). |
| **II. Event Storming 어휘** | ✅ PASS | BoundedContext/Aggregate/Command/Event/Policy 용어 유지. 마법사 단계명은 DDD 표준. 신규 노드 라벨 0. |
| **III. Streaming-First** | ✅ PASS | 마법사·캔버스 자동생성·DDD 검증·내보내기를 `EventSourceResponse`로 스트리밍(child_story/design_reflect 패턴). |
| **IV. Human-in-the-Loop** | ✅ PASS | 전 산출물 propose→confirm; 설계 반영은 기존 change plan/apply·design_reflect 재사용. |
| **V. Feature-Modular** | ✅ PASS | 백엔드 `requirements`(마법사·피보탈) + `ddd_spec`(캔버스 렌더) + `contexts`(분류) 확장. 프런트 `requirements` 미러. 교차의존은 플랫폼/그래프 경유. |
| **VI. Provider-Agnostic LLM** | ✅ PASS | in-process는 `get_llm`; 로컬은 사용자 도구(설정 분리). 하드코딩 없음. |
| **VII. Observable by Default** | ✅ PASS | 신규 엔진은 `SmartLogger` 단계 로그 + correlation ID(030/034 동일). |
| **VIII. Figma SceneGraph** | ➖ N/A | SerializedSceneGraph 비생성. |
| **IX. Plugin↔Backend Dev-Loop** | ➖ N/A | Figma 플러그인 비관여. |

**스키마 변경 정책**: `Event.pivotal`/`hotspot`, `BoundedContext.classification`의 `generic` 값 확장, 캔버스 속성은 **노드 속성 추가**이므로 신규 라벨/관계 규칙에 해당하지 않음. `docs/cypher/schema/03_node_types.cypher` 주석에 속성 의미 보강.

**Gate 결과: PASS** (위반 없음 → Complexity Tracking 비움). **Phase 1 재확인: PASS**(설계가 라벨 0·propose→confirm·SSE·투영 원칙 유지).

## Project Structure

### Documentation (this feature)

```text
specs/035-ddd-discovery-canvases/
├── plan.md              # 본 파일
├── spec.md              # 완료 (7 US)
├── research.md          # Phase 0 (D1–D12)
├── data-model.md        # Phase 1 (Pydantic + 그래프 속성)
├── quickstart.md        # Phase 1 (Q1–Q12 시나리오)
├── contracts/
│   ├── wizard-contract.md                 # US1/US2/US4/US6
│   ├── canvas-contract.md                 # US3/US5
│   └── classification-export-contract.md  # US6 분류 + US7 내보내기
└── checklists/requirements.md             # 완료
```

### Source Code (repository root)

```text
api/features/requirements/
├── routes/
│   ├── ddd_wizard.py            # 신규: 마법사 세션 SSE(시작/단계스트림/answer/confirm)
│   └── pivotal_events.py        # 신규: 피보탈/핫스팟 토글, 피보탈 기반 서브도메인 제안
├── generation/
│   ├── ddd_wizard_engine.py     # 신규: 8단계 오케스트레이션(in-process ↔ claude-ide), local_tooling 재사용
│   └── ddd_export_engine.py     # 신규: 그래프 → .ddd/ 내보내기(+선택 가져오기), ddd_spec 렌더러 호출
├── ddd_wizard/                  # 신규: 세션 상태머신(clarification_session 패턴 복제)
│   ├── wizard_session.py
│   └── step_prompts.py          # 단계별 질문(ddd-starter references 반영)
└── requirements_contracts.py    # 확장: Wizard*/PivotalToggle*/Canvas*/DddExport* DTO

api/features/ddd_spec/
├── renderers/{bc_canvas.py, aggregate_spec.py}   # 재사용(캔버스 뷰 데이터)
└── service.py                                     # 재사용: generate_bounded_context / generate_aggregate

api/features/contexts/router.py   # 확장: classification Literal에 "generic"; BC canvas GET/PATCH

frontend/src/features/requirements/ui/
├── DddWizardPanel.vue           # 신규: 프로파일링→단계 진행 마법사(SSE)
├── BcCanvasTab.vue              # 신규: BC 상세 Canvas 탭
├── AggregateCanvasTab.vue       # 신규: Aggregate Canvas 탭
└── EpicDetail.vue               # 확장: 탭화(+Canvas 탭, BC 클릭 진입)

frontend/src/features/canvas/ui/
└── AggregateViewerInspector.vue # 확장: Canvas 탭 슬롯; CanvasWorkspace BC 클릭 → EpicDetail 오픈
```

**Structure Decision**: 기존 feature-modular 레이아웃(V) 유지. 신규 백엔드 로직은 `requirements` feature의 `generation/`·`ddd_wizard/` 하위 패키지(030/034 동일 구조), 캔버스 렌더는 `ddd_spec` 재사용, 분류는 `contexts` 확장. 프런트는 `requirements` feature에 미러.

## Dependencies

- **spec 034**(현재 같은 트리 미커밋) — `generation/`(child_story/ddd_validation/design_reflect 엔진), `local_tooling`, `requirementGenerationEngine` 토글, `bounded_context_crud`. 035는 이를 직접 재사용하므로 034 머지 후 착수 권장.
- spec 030 clarification 세션/SSE; spec 027 불변조건; spec 028 aggregate 드릴다운; spec 029 robo-spec MCP/`claude_code`; spec 004 change plan/apply; spec 031 언어정책; `ddd_spec` 렌더러; `contexts` classification.
- 로컬 `ddd-starter` 스킬(`~/.claude/skills/ddd-starter`).

## Complexity Tracking

> Constitution Check 위반 없음 — 비움.
