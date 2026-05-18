# Phase 0 Research: Requirements Tab

명세 작성 시 3개 핵심 결정(괘적 캔버스 위치, 영향도 분석 방식, Feature 분류 방식)은 사용자 확인을 거쳐 확정되었으므로 NEEDS CLARIFICATION 없음. 아래는 기존 코드베이스 탐색으로 확인한 사실과 그에 기반한 설계 결정이다.

## R1. Feature 노드 도입 — 메타모델 위치

**Decision**: `Feature`를 신규 노드 타입으로 도입한다. `BoundedContext-[:HAS_FEATURE]->Feature`, `Feature-[:HAS_USER_STORY]->UserStory` 두 관계를 추가한다. UserStory의 BC 소속은 기존 `UserStory-[:IMPLEMENTS]->BoundedContext`를 그대로 유지한다.

**Rationale**:
- 현재 온톨로지에 `Feature` 개념이 없고 BC가 User Story 분류의 최소 단위다(`bounded_contexts.py`: "Do NOT create one BC per function or per small feature"). 명세 FR-006/FR-007이 BC와 User Story 사이 그룹 단위를 명시적으로 요구한다.
- `Requirement`·`UserStory` 노드가 이미 Agile 계층으로 존재하므로 `Feature` 추가는 어휘 일관성을 깨지 않는다(Constitution II note).
- UserStory↔Feature를 별도 `HAS_USER_STORY` 관계로 두면, 한 User Story가 미분류(Feature 없음) 상태를 자연스럽게 표현(관계 부재)할 수 있고 drag-n-drop 재배치는 관계 1개 재연결로 처리된다.

**Alternatives considered**:
- UserStory에 `featureId` 속성만 추가 → 그래프 탐색·impact 분석에서 관계 기반 질의가 불가하고 원칙 I(그래프 기반 추적성)와 어긋남. 기각.
- Feature를 BC의 하위 BC로 표현 → BC 의미(전략적 경계)를 오염시키고 Aggregate/Policy 분류가 꼬임. 기각.

## R2. Feature 멱등 키 & 재인제스트 보존

**Decision**: `Feature.key = "<bc.key>.feature.<slug(featureName)>"`, `Feature.id = randomUUID()` (ON CREATE). neo4j_ops는 MERGE(key) 패턴 사용. UserStory가 수동 재배치(`HAS_USER_STORY`의 `source='manual'`)된 경우 재인제스트 시 LLM 분류가 해당 관계를 덮어쓰지 않는다.

**Rationale**:
- 기존 인제스트는 전 페이즈가 MERGE 기반 증분 upsert(`_bulk_helper.py`, `commands.py`). Feature도 동일 패턴을 따라야 재업로드(FR-013) 시 중복 생성이 없다.
- spec 019에서 `criteriaUserEdited` 플래그로 사용자 편집을 인제스트 재생성으로부터 보호하는 선례가 있다. `HAS_USER_STORY.source='manual'`은 같은 비클로버(non-clobber) 원칙의 적용이다.

**Alternatives considered**: featureName 자체를 키로 사용 → 이름 변경 시 멱등성 깨짐. slug + BC 접두로 안정화. 기각된 대안 없음(보강만).

## R3. 인제스트 페이즈 배치

**Decision**: 신규 `feature_grouping` 페이즈를 **BC 분류 페이즈(`bounded_contexts.py`) 직후, Aggregate 추출 이전**에 배치한다. 입력은 User Story 목록 + 각 US의 BC 배정 결과, 출력은 BC별 Feature 묶음.

**Rationale**:
- Feature는 BC 내부 그룹이므로 BC 배정이 선행되어야 한다(`bounded_contexts.py`가 phase 5에서 `IMPLEMENTS` 생성).
- Aggregate/Command 추출보다 앞서면 Feature 그룹핑이 설계 산출물에 의존하지 않아 독립적이고, SSE 진행률 표시도 요구사항 분해 구간에 자연스럽게 묶인다.
- `ingestion_workflow_runner.py`의 페이즈 시퀀스에 phase 항목 하나를 삽입; `IngestionPhase` enum에 `GROUPING_FEATURES` 추가.

**Alternatives considered**: User Story 추출 페이즈 안에서 동시 분류 → BC 배정 전이라 Feature를 BC에 귀속시킬 수 없음. 기각.

## R4. 자연어 추가 — Human-in-the-Loop 준수

**Decision**: 자연어 입력 추가는 2단계로 한다 — (1) `POST /api/requirements/user-story/propose` 가 LLM 분해 결과(초안 User Story + 제안 BC/Feature)를 **persist 없이** 반환, (2) 사용자가 검토·수정 후 `POST /api/requirements/user-story/confirm` 으로 확정 persist. 수동 입력(역할/행동/효과 직접 타이핑)은 LLM 비관여이므로 단일 `confirm` 호출로 직접 저장.

**Rationale**: Constitution IV는 LLM이 생성한 그래프 변경을 propose → review → apply 하도록 요구한다. 기존 change_management(`/api/change/plan` → `/api/change/apply`)와 chat modify→confirm이 동일 패턴. 자연어 분해는 LLM 생성이므로 동일 절차를 따른다.

**Alternatives considered**: NL 입력 즉시 persist → 원칙 IV 위반. 기각.

## R5. 업로드 증분 upsert 전환

**Decision**: 프런트 `RequirementsIngestionModal.vue`의 업로드 전 기존 데이터 삭제 확인·`/api/graph/clear` 호출 로직을 제거한다(`analyzer` 모드와 동일하게 비삭제). 명시적 삭제는 별도 버튼이 기존 `DELETE /api/ingest/clear-all`을 호출한다. 백엔드 인제스트는 이미 전 페이즈 MERGE 기반이라 변경 불필요.

**Rationale**: 탐색 결과 인제스트 워크플로에 삭제 페이즈가 없고 MERGE만 사용(증분 upsert가 이미 기본). 자동 삭제는 순전히 프런트 모달의 사전 단계였다. 따라서 프런트에서 그 단계만 제거하면 FR-013 충족. `/clear-all`은 그대로 두고 별도 UI 버튼으로 노출(FR-014).

**Alternatives considered**: 백엔드에 별도 upsert 플래그 추가 → 이미 기본 동작이라 불필요. 기각.

## R6. User Story → Command 설계 괘적 로딩

**Decision**: 신규 엔드포인트 `GET /api/requirements/user-story/{id}/design-trace`. `UserStory-[:IMPLEMENTS]->Command`로 기점 Command를 찾고, `HAS_COMMAND`(Aggregate)·`EMITS`(Event)·`TRIGGERS`(Policy)·`INVOKES`(후속 Command) 체인을 제한 깊이(기본 2 hop)로 BFS 순회하여 command-aggregate-event-policy-command-aggregate 부분 그래프(nodes + relationships)만 반환한다.

**Rationale**:
- 탐색 결과 기존 `canvas_subgraph.py`는 노드 ID 집합 기반 generic 서브그래프만 제공하고 command-기점 trace 필터가 없다. `event_modeling.py`는 BFS 체인 순회 패턴(`EMITS→TRIGGERS→INVOKES`)을 이미 구현하고 있어 동일 순회 로직을 재사용한다.
- 반환 포맷을 Design 탭 캔버스(`expand-with-bc` 응답)와 동일한 `{nodes, relationships}` 형태로 맞추면 프런트가 기존 Vue Flow 렌더링·레이아웃(`addNodesWithLayout`)을 그대로 재사용(FR-010).

**Alternatives considered**: 전체 event-modeling 로드 후 클라이언트 필터 → 대형 그래프에서 SC-003(2초) 위반 위험. 전용 엔드포인트로 결정.

## R7. 영향도 분석 재사용 — 백그라운드 비차단

**Decision**: User Story 추가/삭제·Feature 삭제 시 `api/features/requirements/impact_hook.py`가 기존 `change_management`의 impact 분석(`/impact/{user_story_id}` 라우트 + `impact_propagation_engine`)을 백그라운드 태스크(FastAPI `BackgroundTasks` 또는 asyncio task)로 호출한다. 추가로 신규 User Story에 대해 중복·충돌 탐지(기존 US와의 의미 유사도 비교, `related_search.py` 재사용)를 수행한다. 결과는 `Impact Report`로 저장/조회되며 프런트는 폴링 또는 SSE로 비차단 수신한다.

**Rationale**:
- spec 004에서 impact_analysis.py(4-path traversal)·impact_propagation_engine.py(2-hop 반복 확장)·related_search.py가 이미 구현됨. 재구현 대신 호출·확장(원칙 재사용).
- 사용자 답변 = "백그라운드 비차단 분석". 작업 흐름을 막지 않아야 하므로 분석은 mutation 응답과 분리된 비동기 작업으로 실행하고 결과만 사후 알림(FR-019/FR-020).

**Alternatives considered**: 동기 차단 분석 → 사용자 답변과 배치. 기각.

## R8. 트리 4단계 집계 질의

**Decision**: `GET /api/requirements/tree`가 단일 응답으로 Epic(BC) → Feature → UserStory → AcceptanceCriteria(GWT 요약) 계층을 반환한다. 미분류 처리: Feature 없는 US는 해당 BC의 가상 "미분류 Feature" 버킷, BC도 없는 US는 트리 최상위 "미분류" 버킷에 넣는다. AcceptanceCriteria는 `UserStory-[:IMPLEMENTS]->Command-[:HAS_GIVEN|HAS_WHEN|HAS_THEN]->(Given/When/Then)`에서 도출한다.

**Rationale**: 명세 FR-002~FR-005, edge case. GWT는 Command/Policy에 부착(`gwt.py`, schema 노드 10~12). 트리의 AC 노드는 연결 Command의 Given/When/Then을 요약 표시한다. 한 번의 응답으로 트리를 채우면 SC-001(5초 내 탐색)에 유리.

**Alternatives considered**: 단계별 lazy 로딩 엔드포인트 → 호출 왕복 증가. 데이터 규모가 SPA 단일 응답 처리 가능 범위이므로 단일 트리 응답으로 결정(필요 시 BC 단위 lazy 확장 여지 남김).
