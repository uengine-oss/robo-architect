# Phase 1 Data Model: DDD 발견 마법사 & 도메인 캔버스

**신규 Neo4j 노드 라벨/관계: 0건.** 기존 노드 속성 추가 + 신규 Pydantic DTO만.

## 1. Neo4j 그래프 (속성 추가만)

### 1.1 `Event` (피보탈/핫스팟) — US2

| 속성 | 타입 | 의미 |
|---|---|---|
| `pivotal` | bool (default false) | 도메인 상태 전환 분기점(서브도메인 경계 후보) |
| `hotspot` | bool (default false) | 불확실·논쟁 지점 |

`docs/cypher/schema/03_node_types.cypher`의 Event 주석에 두 속성 보강.

### 1.2 `BoundedContext` (캔버스 + 3분류) — US3/US6

| 속성 | 타입 | 의미 |
|---|---|---|
| `classification` | `"core"\|"supporting"\|"generic"` | 기존 enum에 **generic 추가** |
| `purpose` | str? | 한 줄 책임(기존 projection 사용) |
| `domainRoles` | str[] (JSON) | Specification/Execution/Audit/Analysis/Gateway/Notification |
| `ubiquitousLanguage` | str (JSON) | 용어:정의(+타 컨텍스트 충돌 표기) |
| `businessDecisions` | str[] (JSON) | 자율 결정 규칙 |
| `assumptions` | str[] (JSON) | 외부 가정 |
| `version` | int | 낙관적 잠금(기존 classification PATCH 패턴) |

> inbound/outbound 메시지는 기존 그래프 관계(EMITS/INVOKES/TRIGGERS) 투영 — 속성 신설 없음.

### 1.3 `Aggregate` (캔버스) — US5

| 속성 | 타입 | 의미 |
|---|---|---|
| `description` | str? | 한 줄 책임 |
| `stateTransitions` | str (JSON/Mermaid) | 상태 머신(D6) |
| `correctivePolicies` | str[] (JSON) | 불변조건 위협 시 보정 정책 |
| `throughput` | str (JSON) | 동시쓰기/피크/충돌/영속전략 |

> commands/events/invariants는 기존 관계·spec 027 표현 재사용.

### 1.4 비즈니스 컨텍스트/액터 — US4

기존 Actor/Persona 표현(있으면 재사용)에 매핑. 신규 라벨 없이 BC/UserStory의 `role` 등 기존 속성 활용. 매핑 불가 항목은 `.ddd/01-business-context.md`로만 내보내기.

## 2. Pydantic DTO (`requirements_contracts.py` 확장)

### 2.1 마법사 — US1/US2/US4

```python
ProfileAnswer: project_type, ddd_experience, team_size, existing_artifacts[]
WizardStartRequest: scope("greenfield"|"epic"), epicId?, profile: ProfileAnswer, engine?
WizardStepPlan: steps: list[WizardStepRef]   # 추천 단계 조합(skip 표시)
WizardStartResponse: sessionId, recommendedPlan: WizardStepPlan
WizardStepRef: key("understand"|"discover"|…|"code"), title, optional, recommended
WizardAnswerRequest: sessionId, stepKey, answers: dict | pastedDocument?
WizardProposal: stepKey, artifactMarkdown, graphChanges: list[GraphChangePreview]
WizardConfirmRequest: sessionId, stepKey, acceptedChangeIds[]
WizardConfirmResponse: appliedChanges[], errors[]
WizardSessionDTO: sessionId, scope, phase, plan, completedSteps[], artifacts{}
```

SSE 이벤트(`reasoning`/`step_started`/`artifact`/`proposal`/`done`/`error`)는 본문 외 스트림.

### 2.2 피보탈 이벤트 — US2

```python
PivotalToggleRequest: eventId, pivotal?: bool, hotspot?: bool
PivotalToggleResponse: eventId, pivotal, hotspot
SubdomainProposeRequest: sessionId   # 피보탈 경계로 서브도메인 후보 산출
SubdomainProposal: name, responsibility, eventIds[], suggestedClassification
```

### 2.3 캔버스 — US3/US5

```python
BcCanvasDTO: bcId, purpose, classification, domainRoles[], ubiquitousLanguage[], 
             inbound[], outbound[], businessDecisions[], assumptions[], version
BcCanvasPatchRequest: bcId, <위 편집 필드>, ifMatch?
AggregateCanvasDTO: aggregateId, description, stateTransitions, commands[], events[],
                    invariants[], correctivePolicies[], throughput, version
AggregateCanvasPatchRequest: aggregateId, <편집 필드>, ifMatch?
CanvasGenerateRequest: targetId, engine?   # 자동생성(SSE), ddd-spec 재사용
```

### 2.4 분류 — US6 (`contexts`)

```python
Classification = Literal["core","supporting","generic"]   # generic 추가
StrategizeQuestionDTO: bcId, question, options[core/supporting/generic]
```

### 2.5 .ddd 내보내기 — US7

```python
DddExportRequest: outputDir?(default ".ddd"), steps?[]   # 부분 내보내기
DddExportResponse: writtenFiles[], skipped[]
DddImportRequest: outputDir   # 선택 가져오기
DddImportPreview: diffs: list[GraphChangePreview]
DddImportConfirmRequest: acceptedChangeIds[]
```

### 2.6 공용

```python
GraphChangePreview: changeId, action("create"|"update"|"connect"), targetType, 
                    targetId?, before{}, after{}   # model_modifier DraftChange와 정합
LocalToolingStatus  # 재사용(spec 034)
```

## 3. 검증 규칙(스펙 → 모델)

- `WizardStartRequest.scope=="epic"`이면 `epicId` 필수(FR-001).
- `engine=="claude-ide"`면 `local_tooling.probe().ready` 필수, 아니면 409(FR-015).
- 모든 `*ConfirmRequest`는 `acceptedChangeIds` 명시 — 빈 목록이면 그래프 무변경(FR-016).
- `BcCanvasPatchRequest`/`AggregateCanvasPatchRequest`는 속성만 SET, 관계 보존(034 D2).
- `Classification`은 enum 외 값 422(FR-010, contexts 가드 패턴).
- 산출물 언어 = `Accept-Language`/기어 설정(FR-021, spec 031).

## 4. 상태 전이 (마법사 세션)

```
profiling → (plan 확정) → step_running → awaiting_answers → proposing
   → (confirm) → step_running(다음) … → confirmed(전체)
   ↘ discarded / failed
```
중단 후 재개 시 `completedSteps`/`artifacts` 보존(FR-020).
