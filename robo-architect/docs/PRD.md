# PRD (Product Requirements Document)

## Product Name

**Ontology-driven Event Storming & Impact Analysis Engine**

---

## 1. Background & Problem Statement

현재 Event Storming 및 마이크로서비스 설계 과정에서 다음과 같은 문제가 존재한다.

### 1.1 요구사항 변경의 파급 범위 파악 어려움

특정 User Story 변경 시:
- 어떤 Bounded Context가 영향을 받는지
- 어떤 Aggregate / Command / Event / Policy가 영향을 받는지
- 어떤 다른 BC까지 Event를 통해 영향이 전파되는지

정량·구조적으로 설명하기 어려움

### 1.2 Event Storming 결과물의 추적성(Traceability) 부족

- 요구사항 → User Story → BC → Aggregate → Command → Event → Policy 간 연결이 암묵적
- 역설계(Reverse Trace)가 불가능하거나 수작업에 의존

### 1.3 Build Time vs Runtime 변경 전략 구분 부재

- Event 이름/스키마 변경이 다른 BC에 미치는 영향을 자동으로 경고하지 못함
- Cross-BC 이벤트 의존성 파악이 어려움

---

## 2. Product Vision

> **"요구사항의 변화가 시스템 전체에 어떻게 전파되는지를
> 그래프 기반으로 추적·분석·시뮬레이션하는 AI 설계 엔진"**

- Event Storming 결과를 **Ontology + Graph DB (Neo4j)** 로 구조화
- User Story / Event 변경 시 **Cross-BC 영향 범위 자동 탐색**
- 설계자에게 **안전한 변경 전략을 제안 (Human-in-the-loop)**

---

## 3. Goals (Phase 1 – 30일 목표)

### Goal 1 (필수)
- 요구사항 → Event Storming 구조를 **그래프 모델로 생성**
- User Story 기준으로 **전체 영향 트리 탐색 가능**

### Goal 2 (필수)
- Event 변경 시 **영향받는 BC/Policy 조회를 위한 Cypher Query 제공**
- Cross-BC 이벤트 전파 경로 시각화

### Goal 3 (선택)
- 영향 범위를 기반으로 **재생성 대상 노드 식별**
- UI 없이도 **Query 결과로 시연 가능**

### 범위 제외 (Phase 1)
- 완전한 UI 편집기
- 원문 문서 line-level traceability
- 실시간 협업 편집 UI

---

## 4. Core Concepts & Ontology

### 4.1 Node Types (7종)

| Type | 설명 | 필수 속성 |
|------|------|----------|
| **Requirement** | 원 요구사항 (선택) | id, title |
| **UserStory** | "As a … I want …" 단위 | id, role, action |
| **BoundedContext** | 전략적 설계 단위 | id, name |
| **Aggregate** | 전술적 설계 핵심 (일관성 경계) | id, name |
| **Command** | 행위 (사용자 의도) | id, name |
| **Event** | 상태 변화 (도메인 사실) | id, name, version |
| **Policy** | 다른 BC의 Event에 반응하여 Command 실행 | id, name |

### 4.2 Relation Types (7종)

| Relation Type | 방향 | 의미 |
|---------------|------|------|
| **IMPLEMENTS** | UserStory → BC / Aggregate | UserStory가 해당 BC/Aggregate에서 구현됨 |
| **HAS_AGGREGATE** | BC → Aggregate | BC가 Aggregate를 포함 |
| **HAS_POLICY** | BC → Policy | BC가 Policy를 소유 (외부 Event에 반응) |
| **HAS_COMMAND** | Aggregate → Command | Aggregate가 Command를 처리 |
| **EMITS** | Command → Event | Command 실행 시 Event 발생 |
| **TRIGGERS** | Event → Policy | Event가 다른 BC의 Policy를 트리거 |
| **INVOKES** | Policy → Command | Policy가 자신 BC의 Command를 호출 |

### 4.3 Cross-BC Communication Pattern

Event Storming의 핵심 패턴:

```
┌─────────────────────────────────────────────────────────┐
│  BC-A (Publisher)                                       │
│                                                         │
│  Aggregate → Command → Event ─────────────────────────┼──┐
│                                                         │  │
└─────────────────────────────────────────────────────────┘  │
                                                             │ TRIGGERS
┌─────────────────────────────────────────────────────────┐  │
│  BC-B (Subscriber)                                      │  │
│                                                         │  │
│  Policy ←──────────────────────────────────────────────┼──┘
│    │                                                    │
│    └─→ Command → Event                                  │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**핵심 원칙:**
- Event는 발행자 BC에서 생성
- Policy는 구독자 BC에 속함
- Policy는 자신의 BC에 있는 Command만 호출

---

## 5. Functional Requirements

### FR-1. User Story Extraction

**입력:** 자연어 요구사항 문서

**출력:**
- UserStory 노드 집합
- 각 UserStory는 독립적 객체

**예시:**
```
As a customer
I want to cancel my order
So that I can get a refund
```

---

### FR-2. Graph Generation (Event Storming Chain)

1. UserStory → Bounded Context 매핑
2. BC → Aggregate 생성
3. Aggregate → Command 생성
4. Command → Event 생성
5. Event → Policy (다른 BC의) 연결
6. Policy → Command (자신 BC의) 연결
7. 모든 요소를 **Neo4j Graph DB**에 저장

---

### FR-3. Impact Analysis (핵심)

#### 입력
- 변경된 UserStory 또는 Event

#### 처리
- Graph Traversal을 통한 영향 범위 탐색
- Event → Policy → Command 체인 추적
- Cross-BC 영향 분석

#### 출력
- 영향받는 BC 목록
- 영향받는 Policy/Command 목록
- 변경 레벨 분류:
  - **Safe** (Append-only 변경)
  - **Risky** (다수 BC 영향)
  - **Forbidden** (Runtime 금지 변경)

---

### FR-4. Build-Time vs Runtime Change Rules

| 변경 유형 | Build-Time | Runtime |
|----------|------------|---------|
| Event 이름 변경 | ✅ 허용 | ❌ 금지 |
| Event 필드 추가 | ✅ 허용 | ✅ (Append-only) |
| Event 필드 삭제 | ✅ 허용 | ❌ 금지 |
| Event 필드 타입 변경 | ✅ 허용 | ❌ 금지 |
| Command 추가 | ✅ 허용 | ⚠️ 조건부 |
| Policy 로직 변경 | ✅ 허용 | ⚠️ 위험 |

---

### FR-5. Human-in-the-Loop Recommendation

변경 시 시스템이 설계자에게 질문:

> ⚠️ 이 Event는 현재 **3개의 Bounded Context에서 Policy로 구독 중**입니다
> 
> 영향받는 BC:
> - Payment (RefundOnOrderCancelled)
> - Inventory (RestoreStockOnOrderCancelled)
> - Notification (NotifyOnOrderCancelled)
>
> 권장 전략:
> 1. 필드 Append (안전)
> 2. Event V2 생성 후 점진적 마이그레이션
> 3. 전체 BC 동시 수정 (고위험)

---

## 6. Sample Scenario: Order Cancellation

### 6.1 이벤트 흐름

```
Customer가 CancelOrder Command 실행
    ↓
Order BC에서 OrderCancelled Event 발생
    ↓
┌─────────────────────────────────────────┐
│ Payment BC                              │
│   Policy: RefundOnOrderCancelled        │
│   → ProcessRefund Command 실행          │
│   → RefundProcessed Event 발생          │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│ Inventory BC                            │
│   Policy: RestoreStockOnOrderCancelled  │
│   → RestoreStock Command 실행           │
│   → StockRestored Event 발생            │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│ Notification BC                         │
│   Policy: NotifyOnOrderCancelled        │
│   → SendEmail Command 실행              │
│   Policy: NotifyOnRefundProcessed       │
│   → SendEmail Command 실행              │
└─────────────────────────────────────────┘
```

### 6.2 영향도 분석 쿼리 예시

```cypher
// OrderCancelled 이벤트 변경 시 영향받는 BC
MATCH (evt:Event {name: "OrderCancelled"})-[:TRIGGERS]->(pol:Policy)<-[:HAS_POLICY]-(bc:BoundedContext)
MATCH (pol)-[:INVOKES]->(cmd:Command)
RETURN bc.name as affectedBC, pol.name as policy, cmd.name as command;
```

**결과:**
| affectedBC | policy | command |
|------------|--------|---------|
| Payment | RefundOnOrderCancelled | ProcessRefund |
| Inventory | RestoreStockOnOrderCancelled | RestoreStock |
| Notification | NotifyOnOrderCancelled | SendEmail |

---

## 7. Non-Functional Requirements

- **Graph DB:** Neo4j (Cypher 필수)
- **Backend:** Python FastAPI + neo4j-driver
- **Query 기반 결과 출력**만으로 시연 가능
- **UI:** Navigator / Viewer 수준만 고려 (Phase 1)
- **AI Agent:** 생성 + 분석 보조, 최종 판단은 인간

---

## 8. Out of Scope (Phase 1)

- 완전 자동 수정 반영
- Event Sourcing 기반 History Replay
- 실시간 협업 UI
- 문서 원문 라인 추적
- Microservice 단위 관리 (BC 단위로 충분)

---

## 9. Success Criteria (Demo 기준)

- [x] 요구사항 입력 → 그래프 생성
- [x] 특정 UserStory 선택 → 전체 영향 트리 조회
- [x] Cypher Query로 Cross-BC 영향도 범위 설명 가능
- [ ] Runtime 변경 시 위험 경고 시연
- [ ] AI Agent를 통한 그래프 자동 생성

---

## 10. Technical Implementation

### 10.1 Project Structure

```
msaez2/
├── schema/
│   ├── 01_constraints.cypher    # 유일성 제약조건
│   ├── 02_indexes.cypher        # 검색 인덱스
│   ├── 03_node_types.cypher     # 노드 타입 문서
│   └── 04_relationships.cypher  # 관계 타입 정의
├── seed/
│   └── sample_data.cypher       # 주문 취소 시나리오
├── scripts/
│   ├── load_all.py              # 자동 로더
│   └── load_schema.py           # 대화형 로더
├── queries/
│   └── impact_analysis.cypher   # 영향도 분석 쿼리
├── PRD.md                       # 본 문서
└── README.md                    # 사용 가이드
```

### 10.2 Key Cypher Queries

**전체 Event Chain 조회:**
```cypher
MATCH chain = (cmd1:Command)-[:EMITS]->(evt:Event)-[:TRIGGERS]->(pol:Policy)-[:INVOKES]->(cmd2:Command)
RETURN cmd1.name, evt.name, pol.name, cmd2.name;
```

**BC 간 이벤트 의존성:**
```cypher
MATCH (srcBC:BoundedContext)-[:HAS_AGGREGATE]->(agg)-[:HAS_COMMAND]->(cmd)-[:EMITS]->(evt)
MATCH (evt)-[:TRIGGERS]->(pol)<-[:HAS_POLICY]-(tgtBC:BoundedContext)
WHERE srcBC <> tgtBC
RETURN srcBC.name as publisher, evt.name, tgtBC.name as subscriber;
```

---

## 11. Future Roadmap

| Phase | 목표 | 기간 |
|-------|------|------|
| Phase 1 | 그래프 스키마 + 영향도 분석 Query | 30일 |
| Phase 2 | UI Navigator + Drag & Filter | +30일 |
| Phase 3 | 변경 시뮬레이션 & Diff Viewer | +30일 |
| Phase 4 | AI Agent 자동 생성 | +30일 |
| Phase 5 | 코드 생성 연동 | +30일 |

---

## 12. One-line Value Proposition

> **"요구사항 하나의 변화가 시스템 전체에 미치는 영향을
> 그래프로 설명할 수 있는 Event Storming AI"**

---

## Appendix: Glossary

| 용어 | 설명 |
|------|------|
| **Bounded Context (BC)** | 도메인의 논리적 경계. 하나의 유비쿼터스 언어가 적용되는 범위 |
| **Aggregate** | 트랜잭션 일관성을 보장하는 단위. 하나의 Root Entity와 관련 객체들 |
| **Command** | 시스템 상태 변경을 요청하는 의도. 동사형으로 명명 (예: CancelOrder) |
| **Event** | 시스템에서 발생한 사실. 과거형으로 명명 (예: OrderCancelled) |
| **Policy** | 이벤트에 반응하는 비즈니스 규칙. "When [Event] then [Command]" 패턴 |
| **Cross-BC Communication** | 서로 다른 BC 간의 이벤트 기반 통신 |
| **Impact Analysis** | 변경이 시스템 전체에 미치는 영향 분석 |

