# Phase 1 Data Model: Requirements Tab

## §1. Neo4j 그래프 스키마

### 1.1 신규 노드 타입 — `Feature`

`docs/cypher/schema/03_node_types.cypher`에 추가.

| 속성 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `id` | String (UUID) | ✅ | 고유 식별자. ON CREATE 시 `randomUUID()` |
| `key` | String | ✅ | 자연키 — `<bc.key>.feature.<slug(name)>`. 멱등 MERGE 기준 |
| `name` | String | ✅ | Feature 이름 |
| `description` | String | ✕ | 상세 설명 |
| `boundedContextId` | String | ✅ | 소속 BC의 id (조회 편의용 비정규화) |
| `source` | String | ✅ | `"llm"` \| `"manual"` — 자동 도출/수동 생성 구분 |
| `sequence` | Int | ✕ | 트리 내 정렬 힌트 |
| `createdAt` / `updatedAt` | DateTime | ✅ | |

생성 패턴:

```cypher
MATCH (bc:BoundedContext {id: $bcId})
MERGE (f:Feature {key: $featureKey})
ON CREATE SET f.id = randomUUID(), f.createdAt = datetime(), f.source = $source
SET f.name = $name, f.description = $description,
    f.boundedContextId = bc.id, f.updatedAt = datetime()
MERGE (bc)-[:HAS_FEATURE]->(f);
```

### 1.2 신규 관계

`docs/cypher/schema/04_relationships.cypher`에 추가.

| 관계 | 방향 | 속성 | 의미 |
|------|------|------|------|
| `HAS_FEATURE` | `BoundedContext → Feature` | `createdAt` | BC가 Feature를 소유 |
| `HAS_USER_STORY` | `Feature → UserStory` | `createdAt`, `source` (`"llm"`\|`"manual"`), `confidence` (Float, LLM 분류 시) | Feature가 User Story를 포함. **카디널리티: User Story는 최대 1개 Feature에 소속**(없으면 미분류) |

drag-n-drop 재배치 = 기존 `HAS_USER_STORY` 1개를 삭제하고 대상 Feature로 신규 MERGE(`source='manual'`).

### 1.3 제약 / 인덱스

`01_constraints.cypher`: `Feature.id` UNIQUE, `Feature.key` UNIQUE.
`02_indexes.cypher`: `Feature(boundedContextId)` 인덱스, `Feature(name)` 인덱스.

### 1.4 기존 노드/관계 — 변경 없음, 재사용

- `UserStory-[:IMPLEMENTS]->BoundedContext` — Epic 소속 (기존 유지)
- `UserStory-[:IMPLEMENTS]->Command` — 한 US = 한 Command 연결 (기존 유지, 괘적 기점)
- `Command-[:HAS_GIVEN|HAS_WHEN|HAS_THEN]->(Given/When/Then)` — Acceptance Criteria 소스
- `Aggregate-[:HAS_COMMAND]->Command`, `Command-[:EMITS]->Event`, `Event-[:TRIGGERS]->Policy`, `Policy-[:INVOKES]->Command` — 설계 괘적 순회 경로

### 1.5 상태 전이 — `HAS_USER_STORY.source` / `Feature.source`

```
(인제스트 LLM 분류)  → source='llm'
(자연어 propose→confirm) → source='llm'  (LLM 분해 산출물)
(수동 생성/drag-n-drop 재배치) → source='manual'
```

재인제스트 규칙: `source='manual'`인 `HAS_USER_STORY` 관계와 `source='manual'` Feature는 LLM 재분류가 덮어쓰지 않는다(R2 — spec 019 비클로버 선례).

## §2. Pydantic DTO (`api/features/requirements/requirements_contracts.py`)

### 2.1 트리 조회 응답

```
AcceptanceCriterionDTO   { kind: "given"|"when"|"then", name: str, description: str|None }
UserStoryNodeDTO         { id, role, action, benefit, priority, status,
                           commandId: str|None, commandName: str|None,
                           acceptanceCriteria: list[AcceptanceCriterionDTO] }
FeatureNodeDTO           { id, name, description, source, userStories: list[UserStoryNodeDTO] }
EpicNodeDTO              { id (=bcId), name, features: list[FeatureNodeDTO],
                           unassignedFeature: FeatureNodeDTO|None }   # Feature 없는 US 버킷
RequirementsTreeDTO      { epics: list[EpicNodeDTO],
                           unassigned: list[UserStoryNodeDTO] }       # BC도 없는 US
```

### 2.2 Feature CRUD

```
FeatureCreateRequest   { boundedContextId: str, name: str, description: str|None }
FeatureCreateResponse  { feature: FeatureNodeDTO }
FeatureDeleteRequest   { featureId: str, userStoryDisposition: "unassign"|"delete" }
FeatureDeleteResponse  { deleted: bool, affectedUserStoryIds: list[str], impactReportId: str }
```

### 2.3 User Story CRUD / propose-confirm / 재배치

```
UserStoryProposeRequest   { text: str, targetBoundedContextId: str|None }   # 자연어 입력
ProposedUserStory         { role, action, benefit, suggestedBoundedContextId: str|None,
                            suggestedFeatureId: str|None, suggestedFeatureName: str|None,
                            confidence: float, unclear: bool }
UserStoryProposeResponse  { proposals: list[ProposedUserStory], warnings: list[GenerationWarning] }

UserStoryConfirmRequest   { role, action, benefit, priority: str|None,
                            boundedContextId: str|None, featureId: str|None }   # 수동 입력도 동일
UserStoryConfirmResponse  { userStory: UserStoryNodeDTO, impactReportId: str }

UserStoryMoveRequest      { userStoryId: str, targetFeatureId: str }   # drag-n-drop
UserStoryMoveResponse     { userStory: UserStoryNodeDTO, boundedContextChanged: bool }

UserStoryDeleteRequest    { userStoryId: str }
UserStoryDeleteResponse   { deleted: bool, impactReportId: str }
```

### 2.4 설계 괘적

```
DesignTraceResponse  { rootCommandId: str|None,
                       nodes: list[GraphNode],          # Design 탭과 동일 포맷
                       relationships: list[GraphEdge],
                       empty: bool }                    # 연결 Command 없음 → true
```

### 2.5 영향도 리포트

```
ImpactFinding   { kind: "duplicate"|"conflict"|"design_impact",
                  severity: "info"|"warning",
                  message: str,
                  relatedNodeIds: list[str] }
ImpactReportDTO { id: str, status: "running"|"done"|"failed",
                  trigger: "add"|"delete"|"move",
                  findings: list[ImpactFinding], createdAt: datetime }
```

### 2.6 `GenerationWarning` 코드 추가

자연어 분해 시 사용할 경고 코드(기존 GenerationWarning 패턴 따름):

| 코드 | 의미 |
|------|------|
| `requirement_unclear` | 자연어 입력이 모호해 User Story 분해 불확실 |
| `bc_unresolved` | BC 자동 분류 실패 → 미분류 |
| `feature_unresolved` | Feature 자동 분류 실패 → 미분류 |

## §3. 인제스트 페이즈 — `feature_grouping`

- `IngestionPhase` enum에 `GROUPING_FEATURES` 추가.
- `api/features/ingestion/workflow/phases/feature_grouping.py` — 입력: User Story 목록 + BC 배정. BC별로 LLM에 User Story 묶음을 주고 Feature 그룹을 도출. 출력: `{bcId: [Feature{name, description, userStoryIds}]}`.
- `api/features/ingestion/event_storming/neo4j_ops/features.py` — `Feature` MERGE + `HAS_FEATURE`/`HAS_USER_STORY`(`source='llm'`) bulk upsert. `source='manual'` 관계는 보존.
- SSE: `GROUPING_FEATURES` 페이즈 진행률 + Feature 카운트 요약 이벤트.

## §4. 검증 규칙

- `Feature.name`은 BC 범위 내 비어있지 않은 고유 slug. 동일 이름 재요청 시 MERGE로 동일 노드.
- `HAS_USER_STORY`는 User Story당 최대 1개 — 재배치/confirm 시 기존 관계를 먼저 detach.
- `userStoryDisposition='delete'`로 Feature 삭제 시 하위 US도 삭제, `'unassign'`이면 `HAS_USER_STORY`만 detach(US는 미분류로 잔존).
- 자연어 propose는 그래프를 변경하지 않음(읽기/LLM 전용). confirm만 mutation.
- 명시 삭제(`DELETE /api/ingest/clear-all`)는 사용자 확인 필수(기존 동작 유지).
