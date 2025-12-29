# Ontology-driven Event Storming & Impact Analysis Engine

요구사항의 변화가 시스템 전체에 어떻게 전파되는지를 그래프 기반으로 추적·분석·시뮬레이션하는 AI 설계 엔진입니다.

## 목차

- [개요](#개요)
- [프로젝트 구조](#프로젝트-구조)
- [LangGraph Agent](#langgraph-agent)
- [그래프 스키마](#그래프-스키마)
- [설치 및 실행](#설치-및-실행)
- [사용 예제](#사용-예제)
- [영향도 분석 쿼리](#영향도-분석-쿼리)

---

## 개요

### 핵심 가치

> "요구사항 하나의 변화가 시스템 전체에 미치는 영향을 그래프로 설명할 수 있는 Event Storming AI"

### 주요 기능

1. **요구사항 → 그래프 생성**: 자연어 요구사항을 Event Storming 구조로 변환
2. **영향도 분석**: UserStory/Event 변경 시 전체 시스템 영향 범위 자동 탐색
3. **변경 전략 추천**: Build-Time vs Runtime 변경에 따른 안전한 전략 제안

---

## 프로젝트 구조

```
msaez2/
├── agent/                        # LangGraph Event Storming Agent
│   ├── __init__.py              # 패키지 초기화
│   ├── cli.py                   # CLI 인터페이스 (typer + rich)
│   ├── graph.py                 # LangGraph 워크플로우 정의
│   ├── neo4j_client.py          # Neo4j 그래프 작업 클라이언트
│   ├── nodes.py                 # LangGraph 노드 함수들
│   ├── prompts.py               # LLM 프롬프트 템플릿
│   └── state.py                 # 워크플로우 상태 정의
├── schema/
│   ├── 01_constraints.cypher    # 유니크 제약조건 (먼저 실행)
│   ├── 02_indexes.cypher        # 검색 성능용 인덱스
│   ├── 03_node_types.cypher     # 노드 속성 문서 및 생성 템플릿
│   └── 04_relationships.cypher  # 관계 타입 정의
├── seed/
│   └── sample_data.cypher       # 테스트용 샘플 데이터 (주문 취소 시나리오)
├── scripts/
│   ├── load_all.py              # 스키마/데이터 자동 로더
│   └── load_schema.py           # 대화형 로더
├── queries/
│   └── impact_analysis.cypher   # 영향도 분석 쿼리
├── pyproject.toml               # uv 의존성 관리
└── README.md
```

---

## LangGraph Agent

### 개요

LangGraph 기반의 Event Storming 에이전트는 User Story에서 시작하여 완전한 도메인 모델을 자동으로 생성합니다.

**핵심 특징:**
- 🔄 **점진적 처리**: LLM 컨텍스트 제한을 고려하여 User Story를 하나씩 방문
- 👤 **Human-in-the-Loop**: BC, Aggregate, Policy 결정 시 인간 승인 체크포인트
- 📊 **Neo4j 통합**: 생성된 모델을 그래프 DB에 자동 저장
- 🎯 **구조화된 출력**: JSON Schema를 사용한 정확한 LLM 출력

### 워크플로우

```
┌─────────────────────────────────────────────────────────────────┐
│  1. Load User Stories                                           │
│     Neo4j에서 처리되지 않은 User Story 로드                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  2. Identify Bounded Contexts                                   │
│     User Story를 방문하며 BC 후보 식별                            │
│     - 도메인 전문성 차이 고려                                      │
│     - 확장성 요구사항 고려                                         │
│     - 데이터 소유권 고려                                           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  3. ✋ HUMAN APPROVAL: Bounded Contexts                         │
│     BC 후보 검토 및 승인/수정                                      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  4. Breakdown User Stories                                      │
│     각 BC 내에서 User Story 세분화                                │
│     - 하위 작업 식별                                              │
│     - 도메인 개념 추출                                             │
│     - 잠재적 Aggregate/Command 식별                               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  5. Extract Aggregates                                          │
│     각 BC에서 Aggregate 추출                                      │
│     - 일관성 경계 식별                                             │
│     - Root Entity 결정                                           │
│     - 비즈니스 불변식 정의                                         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  6. ✋ HUMAN APPROVAL: Aggregates                               │
│     Aggregate 검토 및 승인/수정                                    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  7. Extract Commands                                            │
│     각 Aggregate에서 Command 추출                                 │
│     - 사용자 의도 기반 명령 생성                                    │
│     - 동사형 네이밍 (CreateOrder, CancelOrder)                    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  8. Extract Events                                              │
│     각 Command에서 Event 추출                                     │
│     - 과거형 네이밍 (OrderCreated, OrderCancelled)                │
│     - 도메인 사실 기록                                             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  9. Identify Policies                                           │
│     Cross-BC 통신을 위한 Policy 식별                              │
│     - "When [Event] then [Command]" 패턴                         │
│     - 이벤트 기반 느슨한 결합                                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  10. ✋ HUMAN APPROVAL: Policies                                │
│      Policy 검토 및 승인/수정                                      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  11. Save to Neo4j                                              │
│      모든 요소를 그래프 DB에 저장                                   │
│      - BC, Aggregate, Command, Event, Policy                    │
│      - 모든 관계 (IMPLEMENTS, HAS_AGGREGATE, etc.)               │
└─────────────────────────────────────────────────────────────────┘
```

### 설치 (uv 사용)

```bash
# uv 설치 (처음 한 번)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 의존성 설치
uv sync

# 환경 변수 설정
cp .env.example .env
# .env 파일에서 OPENAI_API_KEY 또는 ANTHROPIC_API_KEY 설정
```

### CLI 명령어

```bash
# 이벤트 스토밍 워크플로우 시작
uv run msaez run

# Neo4j 연결 및 그래프 통계 확인
uv run msaez status

# 워크플로우 그래프 시각화 (Mermaid)
uv run msaez visualize

# User Story 추가
uv run msaez add-story -r customer -a "cancel my order" -b "I can get a refund"

# User Story 목록 조회
uv run msaez list-stories

# 이벤트 영향도 분석
uv run msaez impact OrderCancelled
```

### Python API 사용

```python
from api.features.ingestion.event_storming import create_event_storming_graph, EventStormingState
from api.features.ingestion.event_storming.graph import EventStormingRunner

# Runner 생성
runner = EventStormingRunner(thread_id="my-session")

# 워크플로우 시작
state = runner.start()

# Human-in-the-loop 처리
while not runner.is_complete():
    if runner.is_waiting_for_human():
        print(runner.get_last_message())
        feedback = input("Your decision: ")
        state = runner.provide_feedback(feedback)
    else:
        break

print("Event Storming Complete!")
```

---

## 그래프 스키마

### 노드 타입 (7종)

| Node Label | 설명 | 필수 속성 |
|------------|------|----------|
| **Requirement** | 원 요구사항 | id, title |
| **UserStory** | "As a ... I want ..." 단위 | id, role, action |
| **BoundedContext** | 전략적 설계 단위 | id, name |
| **Aggregate** | 전술적 설계 핵심 | id, name |
| **Command** | 행위 (명령) | id, name |
| **Event** | 상태 변화 (사실) | id, name, version |
| **Policy** | 다른 BC의 Event에 반응 | id, name |

### 관계 타입 (7종)

```
UserStory ──IMPLEMENTS──> BoundedContext / Aggregate
BoundedContext ──HAS_AGGREGATE──> Aggregate
BoundedContext ──HAS_POLICY──> Policy
Aggregate ──HAS_COMMAND──> Command
Command ──EMITS──> Event
Event ──TRIGGERS──> Policy (다른 BC의 Policy)
Policy ──INVOKES──> Command (자신 BC의 Command)
```

### Event Storming Flow (Cross-BC Communication)

```
┌─────────────────────────────────────────────────────────────┐
│  BC: Order                                                  │
│  ┌───────────┐    ┌─────────────┐    ┌──────────────────┐  │
│  │ Aggregate │───>│   Command   │───>│      Event       │  │
│  │   Order   │    │ CancelOrder │    │ OrderCancelled   │──┼──┐
│  └───────────┘    └─────────────┘    └──────────────────┘  │  │
└─────────────────────────────────────────────────────────────┘  │
                                                                 │ TRIGGERS
┌─────────────────────────────────────────────────────────────┐  │
│  BC: Payment                                                │  │
│  ┌──────────────────────┐    ┌─────────────────┐            │  │
│  │       Policy         │<───┤    (Event)      │<───────────┼──┤
│  │ RefundOnOrderCancel  │    └─────────────────┘            │  │
│  └──────────┬───────────┘                                   │  │
│             │ INVOKES                                       │  │
│             ▼                                               │  │
│  ┌─────────────────┐    ┌──────────────────┐                │  │
│  │     Command     │───>│      Event       │                │  │
│  │  ProcessRefund  │    │ RefundProcessed  │                │  │
│  └─────────────────┘    └──────────────────┘                │  │
└─────────────────────────────────────────────────────────────┘  │
                                                                 │
┌─────────────────────────────────────────────────────────────┐  │
│  BC: Inventory                                              │  │
│  ┌──────────────────────┐                                   │  │
│  │       Policy         │<──────────────────────────────────┼──┤
│  │ RestoreStockOnCancel │                                   │  │
│  └──────────┬───────────┘                                   │  │
│             │ INVOKES                                       │  │
│             ▼                                               │  │
│  ┌─────────────────┐    ┌──────────────────┐                │  │
│  │     Command     │───>│      Event       │                │  │
│  │  RestoreStock   │    │  StockRestored   │                │  │
│  └─────────────────┘    └──────────────────┘                │  │
└─────────────────────────────────────────────────────────────┘  │
                                                                 │
┌─────────────────────────────────────────────────────────────┐  │
│  BC: Notification                                           │  │
│  ┌──────────────────────┐                                   │  │
│  │       Policy         │<──────────────────────────────────┼──┘
│  │ NotifyOnOrderCancel  │                                   │
│  └──────────┬───────────┘                                   │
│             │ INVOKES                                       │
│             ▼                                               │
│  ┌─────────────────┐                                        │
│  │     Command     │                                        │
│  │    SendEmail    │                                        │
│  └─────────────────┘                                        │
└─────────────────────────────────────────────────────────────┘
```

---

## 설치 및 실행

### 사전 요구사항

- Neo4j 4.4 이상 (Community 또는 Enterprise)
- Neo4j Browser 또는 cypher-shell

### 스키마 적용 순서

```bash
# 1. 제약조건 생성
cypher-shell -f schema/01_constraints.cypher

# 2. 인덱스 생성
cypher-shell -f schema/02_indexes.cypher

# 3. 샘플 데이터 로드 (선택)
cypher-shell -f seed/sample_data.cypher
```

### Neo4j Browser에서 실행

```cypher
// 파일 내용을 복사하여 순서대로 실행
// 1. 01_constraints.cypher
// 2. 02_indexes.cypher
// 3. sample_data.cypher
```

### 스키마 확인

```cypher
SHOW CONSTRAINTS;
SHOW INDEXES;
```

---

## 사용 예제

### 노드 생성

```cypher
// UserStory 생성
CREATE (us:UserStory {
    id: "US-NEW",
    role: "seller",
    action: "list my products",
    benefit: "customers can discover and purchase my items",
    priority: "high",
    status: "draft"
});
```

### 관계 생성

```cypher
// UserStory → BoundedContext 연결
MATCH (us:UserStory {id: "US-NEW"})
MATCH (bc:BoundedContext {id: "BC-CATALOG"})
CREATE (us)-[:IMPLEMENTS {
    createdAt: datetime(),
    confidence: 0.90
}]->(bc);
```

### 기본 조회

```cypher
// 모든 UserStory와 구현된 BC 조회
MATCH (us:UserStory)-[:IMPLEMENTS]->(bc:BoundedContext)
RETURN us.role, us.action, bc.name;
```

---

## 영향도 분석 쿼리

### 1. Event 변경 시 영향받는 BC 및 Policy 조회

```cypher
// OrderCancelled 이벤트 변경 시 영향받는 BC
MATCH (evt:Event {name: "OrderCancelled"})-[:TRIGGERS]->(pol:Policy)<-[:HAS_POLICY]-(bc:BoundedContext)
MATCH (pol)-[:INVOKES]->(cmd:Command)
RETURN bc.name as affectedBC, pol.name as policy, cmd.name as command;
```

### 2. Command → Event → Policy → Command 전체 체인

```cypher
// 전체 이벤트 체이닝 조회
MATCH chain = (cmd1:Command)-[:EMITS]->(evt:Event)-[:TRIGGERS]->(pol:Policy)-[:INVOKES]->(cmd2:Command)
RETURN cmd1.name as sourceCmd, evt.name as event, pol.name as policy, cmd2.name as targetCmd;
```

### 3. 특정 UserStory의 영향 범위 탐색

```cypher
// US-001 (주문 취소)가 트리거하는 모든 Policy
MATCH (us:UserStory {id: "US-001"})-[:IMPLEMENTS]->(bc:BoundedContext)-[:HAS_AGGREGATE]->(agg:Aggregate)
MATCH (agg)-[:HAS_COMMAND]->(cmd:Command)-[:EMITS]->(evt:Event)-[:TRIGGERS]->(pol:Policy)
MATCH (pol)<-[:HAS_POLICY]-(targetBC:BoundedContext)
RETURN us.action, evt.name, targetBC.name, pol.name;
```

### 4. Event별 영향받는 BC 수 집계

```cypher
// 각 이벤트별 영향받는 BC 수 (영향 범위 정량화)
MATCH (evt:Event)-[:TRIGGERS]->(pol:Policy)<-[:HAS_POLICY]-(bc:BoundedContext)
RETURN evt.name, evt.version, count(DISTINCT bc) as affectedBCCount
ORDER BY affectedBCCount DESC;
```

### 5. BC 간 이벤트 의존성 분석

```cypher
// BC 간 이벤트 기반 의존 관계
MATCH (sourceBC:BoundedContext)-[:HAS_AGGREGATE]->(agg:Aggregate)-[:HAS_COMMAND]->(cmd:Command)
MATCH (cmd)-[:EMITS]->(evt:Event)-[:TRIGGERS]->(pol:Policy)<-[:HAS_POLICY]-(targetBC:BoundedContext)
WHERE sourceBC <> targetBC
RETURN sourceBC.name as publisher, evt.name as event, targetBC.name as subscriber;
```

### 6. Build-Time vs Runtime 변경 위험도 분석

```cypher
// 영향 범위가 큰 Event 조회 (Breaking Change 위험)
MATCH (evt:Event)-[:TRIGGERS]->(pol:Policy)<-[:HAS_POLICY]-(bc:BoundedContext)
WITH evt, count(DISTINCT bc) as affectedBCs
WHERE affectedBCs > 1
RETURN 
    evt.name,
    evt.version,
    affectedBCs,
    CASE 
        WHEN evt.isBreaking = true THEN "FORBIDDEN"
        WHEN affectedBCs >= 3 THEN "RISKY"
        ELSE "CAUTION"
    END as runtimeChangeRisk;
```

---

## 변경 규칙 (Build-Time vs Runtime)

| 변경 유형 | Build-Time | Runtime |
|----------|------------|---------|
| Event 이름 변경 | ✅ 허용 | ❌ 금지 |
| Event 필드 추가 | ✅ 허용 | ✅ Append-only |
| Event 필드 삭제 | ✅ 허용 | ❌ 금지 |
| Command 추가 | ✅ 허용 | ⚠️ 조건부 |
| Policy 변경 | ✅ 허용 | ⚠️ 위험 |

---

## 다음 단계 (Roadmap)

- [x] Neo4j 그래프 스키마 설계
- [x] 샘플 데이터 (주문 취소 시나리오)
- [ ] Python FastAPI 기반 Impact Analysis API
- [ ] AI Agent 프롬프트 설계
- [ ] 30일 PoC WBS

---

## 라이선스

MIT License

