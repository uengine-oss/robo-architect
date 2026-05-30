# Phase 1 Data Model: Epic / Feature 단위 요구사항 등록·뷰·편집·레이더 필터링

**Feature**: 034-requirement-epic-feature-units | **Date**: 2026-05-30

> **Neo4j 스키마 변경 없음.** 신규 노드 라벨/관계 없음. 기존 노드의 **속성 갱신(rename/description)** 과 새 노드 **생성(기존 라벨)** 만 발생한다. `docs/cypher/schema/` 변경 불필요.

## 1. 그래프 매핑 (기존 노드 재사용)

```
BoundedContext ──[:HAS_FEATURE]──▶ Feature ──[:HAS_USER_STORY]──▶ UserStory
     = Epic                          = Feature                      = User Story
```

| UI 개념 | Neo4j 라벨 | 핵심 속성(기존) | 본 기능에서의 동작 |
|---------|-----------|----------------|--------------------|
| **Epic** | `BoundedContext` | `id`, `key`, `name`, `displayName`, `description`, `owner`, `domainType` | 생성(POST), rename/description 편집(PATCH) |
| **Feature** | `Feature` | `id`(UUID), `key`, `name`, `description`, `boundedContextId`, `source`(llm\|manual), `sequence`, `createdAt`, `updatedAt` | 생성(기존), rename/description 편집(PATCH) |
| **User Story** | `UserStory` | `id`, `role`, `action`, `benefit`, `priority`, `status`, `acceptanceCriteria` | 기존 그대로(회귀 없음) |

**관계 보존 규칙(FR-012)**: 편집(PATCH)은 노드 속성만 `SET` 한다. `HAS_FEATURE`·`HAS_USER_STORY` 관계는 절대 건드리지 않아 하위 항목 연결이 유지된다.

**수동 배치 보호(FR-016)**: `HAS_USER_STORY.source = "manual"` 및 `Feature.source = "manual"` 은 기존 `respect_manual` 로직대로 자동 재분류로 덮어쓰지 않는다.

## 2. 신규/확장 Pydantic 모델 (`api/features/requirements/requirements_contracts.py`)

### Feature 편집
```
FeatureUpdateRequest:
  featureId: str            # 필수
  name: str | None          # 빈 문자열 불가(검증)
  description: str | None
FeatureUpdateResponse:
  feature: FeatureDTO       # 갱신 결과(id, key, name, description, boundedContextId, source)
```

### Epic(BoundedContext) 생성·편집
```
BoundedContextCreateRequest:
  name: str                 # 필수, 비어있을 수 없음
  description: str | None
BoundedContextCreateResponse:
  boundedContext: BoundedContextDTO   # id, key, name, displayName, description

BoundedContextUpdateRequest:
  boundedContextId: str     # 필수
  name: str | None          # 빈 문자열 불가
  description: str | None
BoundedContextUpdateResponse:
  boundedContext: BoundedContextDTO
```

### Epic/Feature AI 제안(propose → confirm)
```
EpicProposeRequest:    { text: str }                       # 자연어
EpicProposeResponse:   { proposals: list[EpicProposal] }   # 미확정 후보(트리 미반영)
  EpicProposal: { name: str, description: str | None }

FeatureProposeRequest: { text: str, boundedContextId: str | None }
FeatureProposeResponse:{ proposals: list[FeatureProposal] }
  FeatureProposal: { name: str, description: str | None, boundedContextId: str | None }
```
> 확정(confirm)은 각각 `POST /bounded-context`(Epic) 및 기존 `POST /feature`(Feature)로 영속 — 별도 confirm 모델 불필요(후보를 그대로 create 요청에 전달).

### 검증 규칙
- `name`: 공백 trim 후 비어있으면 422(FR-011). rename은 동일 부모 내 중복 시 안내(Edge Case) — 차단이 아닌 경고/구분 식별 허용.
- propose 후보 0건/LLM 실패: 200 + 빈 `proposals` → 프런트가 수동 폼으로 폴백(FR-006).

## 3. clarity radar scope (변경 없음 — 참조용)

`ScopeType` enum: `project | bounded_context | feature | user_story`
`compute_clarity_scores_for_scope(user_story_ids, scope_type, scope_id) -> ClarityScores`

10 카테고리 키: `functional_scope, domain_data_model, interaction_flow, non_functional, integration_dependencies, edge_cases, constraints_tradeoffs, terminology, completion_signals, misc_placeholders`

| UI 선택 | scopeType | scopeId |
|---------|-----------|---------|
| 전체/선택 해제 | `project` | `*` |
| Epic 노드 | `bounded_context` | `boundedContext.id` |
| Feature 노드 | `feature` | `feature.id` |
| User Story 노드 | (기존 동작 유지) | — |

집계 대상 user_story_ids는 백엔드가 트리 순회로 해소(기존). 대상 0건이면 중립 점수 반환 → 프런트가 빈/중립 상태로 표시(FR-015).

## 4. 프런트엔드 상태 모델 확장 (`requirements.store.js`)

| 상태/액션 | 종류 | 설명 |
|-----------|------|------|
| `selectedNode: { type: 'epic'\|'feature'\|'userStory', id }` | state | 기존 `selectedUserStoryId`를 일반화. 패널 분기·radar scope의 단일 출처 |
| `clarityScope: { scopeType, scopeId }` | state | 현재 radar 범위 |
| `proposeEpic(text)` / `createEpic(name, description)` | action | `POST /epic/propose` / `POST /bounded-context` |
| `updateEpic(id, {name, description})` | action | `PATCH /bounded-context` |
| `proposeFeature(text, bcId)` / `createFeature(bcId, name, description)`(기존) | action | `POST /feature/propose` / `POST /feature` |
| `updateFeature(id, {name, description})` | action | `PATCH /feature` |
| `selectNode(type, id)` | action | 선택 갱신 + `fetchClarityScores`로 scope 반영 |

기존 `proposeUserStory/confirmUserStory/fetchTree/fetchClarityScores` 등은 변경 없이 유지(회귀 없음).

## 5. 하위 US 자동 생성 (US5) — 모델

> 그래프 영속은 **기존 UserStory 생성 경로** 재사용(신규 노드 없음). 생성은 제안→확정.

```
GenerateChildStoriesRequest:
  scopeType: 'epic' | 'feature'        # 대상 단위
  scopeId: str                          # bcId 또는 featureId
  engine: 'in-process' | 'claude-ide' | None   # None이면 Settings 기본값
GeneratedStory:                          # 미확정 후보
  role: str; action: str; benefit: str
  acceptanceCriteria: list[str]
  targetFeatureId: str | None            # 배치 제안(없으면 신규 Feature 제안)
  rationale: str | None
GenerateChildStoriesProgress(SSE event): # D10 스트리밍
  phase: str; percent: int; partial: list[GeneratedStory]; done: bool
ConfirmChildStoriesRequest:
  scopeType; scopeId; selected: list[GeneratedStory]   # 사용자가 고른 항목만
ConfirmChildStoriesResponse:
  created: list[UserStoryDTO]
```

**엔진 선택값**: `Settings.requirementGenerationEngine`(D14). 그래프 아님.
- 프런트: `SettingsPanel.vue` + Pinia(예: `useUiSettings()`), 값 `'in-process' | 'claude-ide'`.
- Electron: `DesktopSettings.requirementGenerationEngine`(`ipc-contract.ts`), 기본 `'in-process'`, settings 마이그레이션으로 채움.

**로컬 도구 가용성(US5 claude-ide)**:
```
LocalToolingStatus:
  claudeInstalled: bool                 # shutil.which("claude")
  speckitInstalled: bool                # speckit/robo-spec 스킬 존재
  missing: list[str]; installHint: str  # 설치 안내(FR-021)
```

## 6. DDD 적합성·정합성 검증 (US6) — 모델

```
ValidateRequest:
  targetType: 'epic' | 'feature' | 'userStory'
  target: { name, description, boundedContextId?, featureId?, role?, action?, benefit? }
  mode: 'pre-create' | 'post-create'
ValidationFinding:
  kind: 'wrong_bc' | 'oversized_feature' | 'spec_conflict'
  severity: 'info' | 'warning'
  message: str
  affected: list[str]                   # 관련 BC/Feature/US/spec 식별자
  suggestion: CorrectionProposal        # 교정안
CorrectionProposal:
  action: 'replace_bc' | 'split' | 'merge' | 'differentiate'
  details: dict                         # 예: 권장 bcId, 분할된 Feature/US 목록
ValidateResponse:
  ok: bool                              # findings 비면 true(FR-028)
  findings: list[ValidationFinding]
  source: 'in-process' | 'robo-skill'   # 어떤 경로로 검증했는지
```

**스킬 경로(claude-ide/robo-spec)**: `skills/robo-spec/robo-validate/SKILL.md`(신규) 또는 `speckit-specify` override. robo-spec **MCP 툴**로 BC 목록(`list_design_elements`)·BC 설계(`get_bc_design`)·기존 spec 컨텍스트를 읽어 동일한 `ValidationFinding`을 산출. 비차단 — 경고만(FR-028), 단 정의된 BC 0건이면 BC 선행 요구.

## 7. 설계 자동 반영 (US7) — 모델

> 신규 노드/관계 0건. **미반영 판정 = `IMPLEMENTS→Command` 부재**(design-trace). 설계 생성은 기존 change_management `/api/change/plan`→`/apply` 재사용.

```
PendingDesignResponse:
  pending: list[ PendingUS ]            # 설계 미반영 US
  PendingUS: { userStoryId, role, action, benefit, featureId, boundedContextId }
DesignReflectRequest:
  userStoryIds: list[str]               # 반영할 미반영 US(사용자 동의 대상)
DesignReflectProgress(SSE event):       # D10
  userStoryId: str; phase: str; percent: int
  changeProposal: ChangeProposal | None # 기존 change-plan 산출(journey/aggregate 변경)
  done: bool
# 확정: 기존 POST /api/change/apply 로 사용자 확인 후 그래프 반영(HITL)
```

| US7 개념 | 기존 자산 |
|----------|-----------|
| 미반영 US 식별 | `design_trace.py`의 `IMPLEMENTS→Command` 부재(empty:true) → 신규 `GET /user-stories/pending-design` |
| 설계 변경 생성 | `change_management` `POST /api/change/plan`(propose) |
| 설계 변경 반영 | `POST /api/change/apply`(HITL) |
| journey/Aggregate | 기존 Event Modeling/Aggregate 노드(신규 라벨 없음) |
| 탭 진입 훅 | `App.vue` `_onSwitchTab`('Event Modeling'→`EventModelingPanel`, 'Design'→`CanvasWorkspace`) |
