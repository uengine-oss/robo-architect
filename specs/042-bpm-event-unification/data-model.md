# Phase 1 Data Model: BPM ↔ Event Modeling 통합

## Neo4j 스키마 변경: **0건**

본 피처는 **읽기 전용 투영 + UI 정리**다. 신규 노드 라벨/관계/속성 0건. 아래는 *이미 영속된* 그래프 요소(재사용 대상)와, 추가하는 **API DTO**만 기술한다.

### 재사용하는 기존 그래프 요소 (변경 없음)

| 요소 | 출처 | 용도 |
|---|---|---|
| `(:BpmTask {id, session_id, name, …})` | A2A 어댑터 → `event_storming_bridge` | BPM task 척추(trace 루트 키) |
| `(:Command)-[:PROMOTED_FROM {via:'task'}]->(:BpmTask)` | persistence.py L422 | task의 시스템 체인 루트 진입 |
| `(:UserStory\|:Aggregate\|:Event\|:Policy\|:ReadModel)-[:PROMOTED_FROM]->(:BpmTask)` | persistence.py | task 귀속 요소(검증·집계) |
| `(:Aggregate)-[:HAS_COMMAND]->(:Command)` | persistence.py L401 | 모달 스티커 확장 |
| `(:UI)-[:ATTACHED_TO]->(:Command)` | (event storming) | task → UI 도달 경로(D1) |
| `(:Command)-[:EMITS]->(:Event)` | persistence.py L461 | 모달 체인 확장 |
| `(:Event)-[:TRIGGERS]->(:Policy)-[:INVOKES]->(:Command)` | event storming | 정책 체인 확장 |
| `(:n)-[:HAS_PROPERTY]->(:Property)` | event storming | 스티커 속성 표시(`_attach_properties`) |

### 핵심 읽기 쿼리 (신규 라우트)

> **실측 정정(2026-06-10):** 현재 그래프의 BPM↔ES 브리지는 `(:Command)-[:PROMOTED_FROM]->(:BpmTask)` 가 아니라 **`(:BpmTask)-[:PROMOTED_TO]->(:UserStory)-[:IMPLEMENTS]->(:Command)`** 다(라이브 세션 `0dcf8cc7` 확인: `PROMOTED_TO` 20건, `PROMOTED_FROM` 0건). 라우트는 두 스키마를 **모두 커버**한다.

```cypher
// 1) task 존재 확인
MATCH (t:BpmTask {id: $tid}) RETURN t.id AS id

// 2) task에 귀속된 루트 Command 집합 (두 스키마 union)
MATCH (t:BpmTask {id: $tid})
OPTIONAL MATCH (t)-[:PROMOTED_TO]->(:UserStory)-[:IMPLEMENTS]->(c1:Command)   // 현행
OPTIONAL MATCH (c2:Command)-[:PROMOTED_FROM]->(t)                            // 대체
WITH collect(DISTINCT c1.id) + collect(DISTINCT c2.id) AS ids
UNWIND ids AS cid
WITH DISTINCT cid WHERE cid IS NOT NULL
RETURN cid

// 3) 이후 확장은 design_trace.py의 _expand_trace와 동일:
//    Aggregate-[:HAS_COMMAND]->Command, UI-[:ATTACHED_TO]->Command,
//    Command-[:EMITS]->Event-[:TRIGGERS]->Policy-[:INVOKES]->Command
//    (bounded depth ≤ 5, 기본 2) + _attach_properties
```

## API DTO

### 재사용: `DesignTraceResponse` (수정 없음)

```python
# api/features/requirements/requirements_contracts.py L456 (기존)
class DesignTraceResponse(BaseModel):
    rootCommandId: str | None = None   # task 라우트에서는 첫 루트 Command(또는 None)
    nodes: list[dict] = []             # {id, type, name, properties, …}
    relationships: list[dict] = []     # {source, target, type}
    empty: bool = False
```

신규 라우트는 동일 응답 형태를 반환한다(프런트 `DesignTraceCanvas`가 그대로 소비). 별도 DTO 신설 불필요 — `rootCommandId`는 task의 첫 루트 Command id(없으면 None)로 채운다.

> 선택: 의미 명료화를 위해 `BpmTaskTraceResponse(DesignTraceResponse)` 빈 서브클래스를 둘 수 있으나, 형태가 동일하므로 **`DesignTraceResponse` 직접 사용**을 기본으로 한다(코드 표면 최소화).

### Query params

| param | 기본 | 범위 | 의미 |
|---|---|---|---|
| `depth` | 2 | 1~5 | frontier 확장 깊이(설계-궤적과 동일 상한) |
| `session_id`(`$sid`) | 현재 세션 | — | 멀티세션 스코프(기존 패턴) |

## 상태 전이 / 검증 규칙

- **상태 없음** — 읽기 전용. 그래프 변이 없음.
- **검증**: 모달이 보여주는 노드 집합 = 쿼리 2)+3) 결과와 1:1(SC-002). task에 promoted Command 0 → `empty=True`(US2 AC3).

## Big picture 제거 (데이터 측면)

- 그래프 노드/관계 삭제 **아님** — 빅픽처는 별도 노드 라벨이 아니라 `bigpicture-timeline` 쿼리의 *투영*이었음. 백엔드 라우트 + 프런트 store/panel만 제거.
- `(:BoundedContext)` 등 빅픽처가 읽던 노드는 다른 뷰가 계속 사용 → 불변.
