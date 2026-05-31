# Phase 0 Research: DDD 발견 마법사 & 도메인 캔버스

기존 코드와 `ddd-starter` 스킬을 대조하여 결정한 항목. 모든 NEEDS CLARIFICATION 해소됨.

## D1 — 마법사 세션 인프라

**Decision**: spec 030 `requirements/clarification_agent/clarification_session.py`의 휘발성 in-process 세션 상태머신을 복제하여 `requirements/ddd_wizard/wizard_session.py`로 만든다. 상태: `profiling → step_running → awaiting_answers → proposing → confirmed`(단계 반복), 그리고 `discarded/failed`.

**Rationale**: 030은 `analyzing→awaiting_answers→encoding→completed` 상태머신 + SSE + answer/apply를 이미 검증. 세션은 그래프 비저장(Constitution I)이며 030과 동일하게 in-process dict로 둔다.

**Alternatives**: Neo4j에 세션 노드 저장 → Constitution I("병렬 model 상태 금지")와 휘발 세션 성격에 맞지 않아 기각.

## D2 — 이원화 생성 엔진 재사용

**Decision**: spec 034 `requirements/generation/child_story_engine.py` 패턴을 그대로 따른다. 요청 `engine: "in-process" | "claude-ide"`, `claude-ide`면 `generation/local_tooling.probe()`로 preflight(미설치 시 409 + 설치 안내). in-process는 `get_llm`.

**Rationale**: 034가 이미 동일 토글(`requirementGenerationEngine`)을 프런트(SettingsPanel/RequirementsPanel/store)·백엔드(`local_tooling`, `GET /local-tooling/status`)에 구현. 캔버스/마법사/DDD검증 생성에 그대로 적용해 일관성·재사용 극대화.

**Alternatives**: 신규 엔진 추가 → spec FR-014/Constitution VI 위배, 기각.

## D3 — SSE 진행 스트리밍

**Decision**: `sse_starlette.EventSourceResponse` + `asyncio.Queue`/`create_task` 패턴(child_story_generation.py, chat_edit.py)을 신규 라우트(`ddd_wizard.py`)에 동일 적용. 이벤트 종류: `reasoning`/`step_started`/`artifact`/`proposal`/`error`/`done`.

**Rationale**: Constitution III + 034 검증 패턴. EventSource는 프런트 기존 배선 재사용.

## D4 — Bounded Context Canvas 데이터·렌더

**Decision**: 그래프 BC 노드 → `ddd_spec/projection.BoundedContextProjection`(purpose, strategic, inbound/outbound flows, key_terms) 투영을 캔버스 뷰 데이터로 사용. 자동생성은 `POST /api/ddd-spec/generate-bounded-context`·`renderers/bc_canvas.py` 재사용. 편집은 BC 노드 속성 PATCH(아래 D9).

**Rationale**: 캔버스 렌더러·프로젝션이 이미 존재(책임/전략분류/유비쿼터스 언어/인·아웃바운드 흐름 필드 보유) → 신규 모델 불필요. 그래프 투영이라 Constitution I 부합.

**Alternatives**: 신규 Canvas 노드 라벨 → 기각(라벨 0 정책).

## D5 — Aggregate Design Canvas 데이터·렌더

**Decision**: `AggregateProjection`(commands/events/policies/attributes/invariants) + `renderers/aggregate_spec.py` + `POST /api/ddd-spec/generate-aggregate` 재사용. 상태전이는 ADC용 신규 표현 필요(아래 D6). 불변조건은 spec 027 표현 재사용.

**Rationale**: 프로젝션·렌더러 존재. spec 028 `AggregateViewerInspector`에 탭으로 장착.

## D6 — 상태 전이(State Transition) 표현

**Decision**: Aggregate 상태 전이는 ADC 캔버스 필드로 두되, 그래프에는 `Aggregate.stateTransitions`(JSON 문자열 속성, Mermaid stateDiagram 소스 or 구조화 목록)로 보관. 신규 노드/관계 없음.

**Rationale**: 상태머신을 1급 노드로 만들면 라벨 증가. 속성 보관이 라벨 0 정책에 부합하고 캔버스 렌더(Mermaid)에 충분.

**Alternatives**: State/Transition 노드화 → 기각(과설계 + 라벨 증가).

## D7 — 피보탈 이벤트 / 핫스팟

**Decision**: 기존 `Event` 노드에 불리언 속성 `pivotal`, `hotspot` 추가. EventStorming 단계에서 LLM이 후보를 표시하고 사용자가 토글. Decompose 단계는 `pivotal=true` 이벤트를 경계로 서브도메인을 제안.

**Rationale**: spec D12 정신(속성으로 의미 부여). 기존 event_storming 도출·EventModeling `sequence`와 공존. 신규 라벨 0.

**Alternatives**: PivotalEvent 라벨/관계 → 기각.

## D8 — 서브도메인 → BC 매핑

**Decision**: 서브도메인은 BC 후보로서 propose→confirm 시 기존 `BoundedContext` 노드로 생성(requirements `bounded_context_crud` `POST /bounded-context` 재사용). 별도 Subdomain 노드를 만들지 않고, 확정 전에는 세션 내 후보로만 존재.

**Rationale**: spec 매핑(Epic=BoundedContext). 라벨 0.

## D9 — 캔버스 편집(쓰기) 경로

**Decision**: BC 캔버스 편집은 `contexts/router.py`에 BC 속성 PATCH(purpose/ubiquitousLanguage/businessDecisions/assumptions/domainRoles)를 추가하거나 기존 requirements `PATCH /bounded-context`(속성만 SET, 관계 보존; spec 034 D2) 확장. Aggregate 캔버스 편집은 기존 aggregate 속성 PATCH(model_modifier/`AggregateViewerInspector` 저장 경로) 확장. 모두 낙관적 버전(`If-Match`, contexts 패턴) 사용.

**Rationale**: 034 D2가 "속성만 SET, 관계 보존" 패턴을 이미 정의. contexts classification PATCH가 `If-Match` 낙관적 버전을 보유 → 동일 적용.

## D10 — 전략 분류 3분류 확장

**Decision**: `contexts/router.py`의 `Classification = Literal["core","supporting"]`를 `["core","supporting","generic"]`으로 확장. GET/PATCH 가드·프런트 배지 동시 수정. Strategize 단계 질문("외부 아웃소싱 시 고객이 알아챌까?")으로 제안.

**Rationale**: 현재 generic 미지원(코드 확인). 스킬은 3분류 필수. 단순 enum 확장 + 가드 한 줄.

**Alternatives**: 별도 분류 필드 신설 → 기각(기존 `classification` 속성 재사용이 단순).

## D11 — .ddd 내보내기(보조 산출물)

**Decision**: `generation/ddd_export_engine.py`가 그래프를 읽어 `ddd_spec` 렌더러(bc_canvas/aggregate_spec/context_map/domain_terms)로 `.ddd/` 트리(`00-plan`~`08-aggregates/`)를 생성. 기존 `ddd_spec`은 `specs/bounded-contexts/`에 쓰므로 출력 경로만 `.ddd/`로 매개변수화. 가져오기(import)는 선택: diff→propose→confirm.

**Rationale**: 그래프=원천(Q1). 렌더러 재사용. 양방향 충돌은 가져오기에서만 발생하므로 낙관적 안내(spec 034 D7).

## D12 — DDD 검증 재사용

**Decision**: 마법사 게이트 체크(스킬의 단계별 체크리스트)와 spec 034 `ddd_validation_engine`(wrong_bc/oversized_feature/spec_conflict)을 결합. 마법사 단계 완료 시 해당 검증을 비차단으로 제시.

**Rationale**: 034가 검증 엔진을 이미 구현(in-process/claude-ide 미러). 중복 제거.

## D13 — 마법사 = ingestion 설계 기계 오케스트레이터

**Decision**: 마법사는 자체 그래프 생성기를 두지 않고 기존 경로를 호출하는 **오케스트레이터**다. Decompose→`POST /bounded-context`(`bounded_context_crud`), Code/설계→`POST /api/ingest/user-stories/design`(`incremental_design_runner`, clear 없는 증분), 마무리→spec 034 `design_reflect`. `ddd_wizard_engine`은 단계 진행·HITL·SSE·프롬프트만 담당.

**Rationale**: 사용자 확정("기존 ingestion 설계 기계 재사용"). 커맨드/이벤트/애그리거트 도출 로직을 두 벌 유지하지 않음(중복 제거, Constitution V). 증분 실행기는 이미 SSE·MERGE·범위 한정·design_reflect 연동을 구현.

**Alternatives**: 마법사 전용 LLM 생성기 → 기각(로직 이원화, 회귀 위험).

## D14 — 전체 ingestion clear 충돌 / 피보탈 보존

**Decision**: 마법사는 **clear 하는 전체 ingestion(`/api/ingest/upload`)을 트리거하지 않는다**. 모든 확정은 비-clear 증분 경로로 반영. 한편 (a) `ingestion_workflow_runner`의 clear 보존 목록/속성 carry-over에 `Event.pivotal`/`hotspot`와 마법사 확정 BC 속성(purpose/classification/캔버스 필드)을 포함시키고, (b) 사용자가 마법사 후 "문서 업로드"(전체)를 실행하면 모델 재구축 사전 경고를 띄운다.

**Rationale**: 전체 ingestion은 의도적으로 이벤트스토밍 노드를 clear→재구축. 보존 장치 없이는 마법사 산출물(특히 피보탈 표시·전략 분류)이 소실. 커맨드 중심 재도출은 피보탈 플래그를 알지 못하므로 carry-over 필요. 이벤트 중복은 병합 후보(D7/FR-026).

**Alternatives**: 전체 ingestion이 마법사 BC를 MERGE 입력으로 받아 경계를 존중 → 후속 개선(현 `bounded_contexts.py`는 LLM 추정). 우선은 보존+경고로 안전 확보.

## 미해결/위험

- **R1**: spec 034가 같은 작업 트리에서 미커밋(M/??) 상태 — 035는 034의 `generation/`·`local_tooling`·`requirementGenerationEngine` 구현에 의존. 034 머지 후 진행 권장(plan Dependencies 참조).
- **R2**: `ddd_spec` 출력 경로 매개변수화 시 기존 `specs/bounded-contexts/` 생성 경로 회귀 주의(out-of-band 회귀 테스트).
- **R3**: 로컬 `claude-ide` 엔진의 `ddd-starter` 스킬 호출은 PTY/MCP 경유 — 장시간·환경 의존. in-process를 기본 엔진으로 둔다.
