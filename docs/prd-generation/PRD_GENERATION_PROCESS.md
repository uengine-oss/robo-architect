# 이벤트 스토밍 모델 기반 PRD 생성 과정 및 구조

## 목차

1. [개요](#개요)
2. [전체 프로세스 흐름](#전체-프로세스-흐름)
3. [데이터 구조 및 Neo4j 쿼리](#데이터-구조-및-neo4j-쿼리)
4. [PRD 생성 함수 및 아티팩트](#prd-생성-함수-및-아티팩트)
5. [API 엔드포인트](#api-엔드포인트)
6. [생성되는 파일 구조](#생성되는-파일-구조)
7. [기술 스택 설정](#기술-스택-설정)

---

## 개요

이 문서는 **이벤트 스토밍 모델(Event Storming Model)**을 기반으로 **PRD(Product Requirements Document)** 및 개발 에이전트 컨텍스트 파일들을 생성하는 과정과 구조를 설명합니다.

### 핵심 개념

- **이벤트 스토밍 모델**: Neo4j 그래프 데이터베이스에 저장된 DDD(Domain-Driven Design) 기반 도메인 모델
- **PRD 생성**: 그래프에서 Bounded Context, Aggregate, Command, Event 등의 정보를 추출하여 문서화
- **아티팩트 생성**: PRD 외에도 AI 개발 에이전트(Claude, Cursor 등)를 위한 컨텍스트 파일 생성

### 관련 문서

- **[PRD Cursor 개선 사항](PRD_CURSOR_IMPROVEMENTS.md)**: Cursor IDE 기반 PRD 생성에서 개선된 내용들 정리
  - Database 관련 지시사항 강화
  - Cursor @mention 기능 활용
  - 메인 PRD에서 Spec과 Rules 참조 명확화
  - UI Wireframe, Database, API, 서비스별 페이지 구현 가이드
  - Event 송수신 및 서비스별 의존성 관리
  - 향후 Claude Agent 적용 시 고려사항 포함

---

## 전체 프로세스 흐름

### 1. 이벤트 스토밍 모델 생성 (사전 단계)

이벤트 스토밍 워크플로우를 통해 Neo4j에 도메인 모델이 생성됩니다:

```
요구사항 문서
    ↓
User Story 추출
    ↓
Bounded Context 식별
    ↓
Aggregate 추출
    ↓
Command 추출
    ↓
Event 추출
    ↓
Policy 식별
    ↓
Property, ReadModel, UI, GWT 생성
    ↓
Neo4j 그래프 저장
```

### 2. PRD 생성 프로세스

```
사용자 요청 (node_ids 선택 또는 전체)
    ↓
Neo4j에서 Bounded Context 데이터 조회
    ├─ Aggregate 및 Properties
    ├─ Command 및 Properties
    ├─ Event 및 Properties
    ├─ ReadModel 및 Properties
    ├─ Policy
    ├─ UI Wireframes
    └─ GWT Test Cases
    ↓
Tech Stack 설정 적용
    ↓
다양한 아티팩트 생성
    ├─ PRD.md (메인 PRD)
    ├─ CLAUDE.md (Claude AI 컨텍스트)
    ├─ .cursorrules (Cursor IDE 전역 규칙)
    ├─ specs/{bc_name}_spec.md (BC별 상세 스펙)
    ├─ .cursor/rules/{bc_name}.mdc (BC별 Cursor 규칙, ai_assistant=cursor일 때)
    │   또는 .claude/agents/{bc_name}_agent.md (BC별 Claude 에이전트, ai_assistant=claude일 때)
    ├─ README.md (프로젝트 개요)
    └─ Docker 관련 파일 (선택적)
    ↓
ZIP 파일로 패키징
    ↓
다운로드 제공
```

---

## 데이터 구조 및 Neo4j 쿼리

### Bounded Context 데이터 조회

PRD 생성의 핵심은 `get_bcs_from_nodes()` 함수가 Neo4j에서 Bounded Context와 관련된 모든 데이터를 조회하는 것입니다.

#### 1. 노드 ID 해석 (`get_bcs_from_nodes`)

**입력**: `node_ids` (선택적)
- `None` 또는 빈 리스트: 모든 Bounded Context 포함
- 특정 노드 ID 리스트: 해당 노드가 속한 Bounded Context 자동 탐색

**노드 ID 해석 로직**:
```cypher
// 1. 직접 BC 노드
MATCH (bc:BoundedContext {id: nodeId})

// 2. BC에 포함된 노드 (Aggregate, Policy, ReadModel, UI)
MATCH (bc)-[:HAS_AGGREGATE|HAS_POLICY|HAS_READMODEL|HAS_UI*1..3]->(n {id: nodeId})

// 3. Command를 통한 BC 탐색
MATCH (bc)-[:HAS_AGGREGATE]->(agg)-[:HAS_COMMAND]->(cmd:Command {id: nodeId})

// 4. Event를 통한 BC 탐색
MATCH (bc)-[:HAS_AGGREGATE]->(agg)-[:HAS_COMMAND]->(cmd)-[:EMITS]->(evt:Event {id: nodeId})

// 5. Property를 통한 BC 탐색
MATCH (prop:Property {id: nodeId})
MATCH (bc)-[:HAS_AGGREGATE]->(agg)-[:HAS_PROPERTY]->(prop)
// 또는 Command, Event, ReadModel의 Property
```

#### 2. Bounded Context 상세 데이터 조회 (`fetch_bc_data`)

각 BC ID에 대해 다음 정보를 조회합니다:

```cypher
MATCH (bc:BoundedContext {id: $bc_id})

// 1. Aggregate 및 Properties
OPTIONAL MATCH (bc)-[:HAS_AGGREGATE]->(agg:Aggregate)
OPTIONAL MATCH (agg)-[:HAS_PROPERTY]->(aggProp:Property)

// 2. Command 및 Properties
OPTIONAL MATCH (agg)-[:HAS_COMMAND]->(cmd:Command)
OPTIONAL MATCH (cmd)-[:HAS_PROPERTY]->(cmdProp:Property)

// 3. Event 및 Properties
OPTIONAL MATCH (cmd)-[:EMITS]->(evt:Event)
OPTIONAL MATCH (evt)-[:HAS_PROPERTY]->(evtProp:Property)

// 4. ReadModel 및 Properties
OPTIONAL MATCH (bc)-[:HAS_READMODEL]->(rm:ReadModel)
OPTIONAL MATCH (rm)-[:HAS_PROPERTY]->(rmProp:Property)

// 5. Policy (Event 트리거 및 Command 호출)
OPTIONAL MATCH (bc)-[:HAS_POLICY]->(pol:Policy)
OPTIONAL MATCH (triggerEvt:Event)-[:TRIGGERS]->(pol)
OPTIONAL MATCH (pol)-[:INVOKES]->(invokeCmd:Command)

// 6. UI Wireframes
OPTIONAL MATCH (bc)-[:HAS_UI]->(ui:UI)

// 7. GWT Test Cases
OPTIONAL MATCH (bc)-[:HAS_AGGREGATE]->(:Aggregate)-[:HAS_COMMAND]->(cmd2:Command)-[:HAS_GWT]->(gwt:GWT)
OPTIONAL MATCH (bc)-[:HAS_POLICY]->(pol2:Policy)-[:HAS_GWT]->(gwt2:GWT)
```

**반환 데이터 구조**:
```python
{
    "id": "bc-uuid",
    "name": "Order Management",
    "description": "주문 관리 도메인",
    "aggregates": [
        {
            "id": "agg-uuid",
            "name": "Order",
            "rootEntity": "Order",
            "invariants": ["Order total must be positive", "Order must have at least one item"],
            "enumerations": [{"name": "OrderStatus", "values": ["PENDING", "CONFIRMED", "SHIPPED"]}],
            "valueObjects": [{"name": "Address", "properties": [...]}],
            "properties": [
                {
                    "id": "prop-uuid",
                    "name": "orderId",
                    "type": "String",
                    "isKey": true,
                    "isForeignKey": false,
                    "fkTargetHint": "Aggregate:Customer:id",
                    "description": "주문 ID"
                }
            ],
            "commands": [
                {
                    "id": "cmd-uuid",
                    "name": "CreateOrder",
                    "actor": "customer",
                    "category": "Create",
                    "inputSchema": '{"items": "array", "shippingAddress": "string"}',
                    "description": "Creates a new order with items and customer information",
                    "properties": [...]
                }
            ],
            "events": [
                {
                    "id": "evt-uuid",
                    "name": "OrderCreated",
                    "version": "1.0.0",
                    "schema": '{"orderId": "string", "customerId": "string"}',
                    "description": "A new order has been created",
                    "properties": [...]
                }
            ]
        }
    ],
    "readmodels": [
        {
            "id": "rm-uuid",
            "name": "OrderList",
            "description": "List of orders for a customer",
            "provisioningType": "CQRS",
            "actor": "customer",
            "isMultipleResult": "list",
            "properties": [...]
        }
    ],
    "policies": [
        {
            "id": "pol-uuid",
            "name": "RefundOnOrderCancellation",
            "description": "주문 취소 시 환불 처리",
            "triggerEventId": "evt-123",
            "triggerEventName": "OrderCancelled",
            "triggerEventBCId": "bc-order",
            "triggerEventBCName": "Order Management",
            "invokeCommandId": "cmd-456",
            "invokeCommandName": "ProcessRefund",
            "invokeCommandBCId": "bc-payment",
            "invokeCommandBCName": "Payment Processing"
        }
    ],
    "uis": [...],
    "gwts": [
        {
            "id": "gwt-uuid",
            "parentType": "Command",
            "parentId": "cmd-uuid",
            "givenRef": {"referencedNodeId": "agg-uuid", "name": "Order", "description": "..."},
            "whenRef": {"referencedNodeId": "cmd-uuid", "name": "CreateOrder", "description": "..."},
            "thenRef": {"referencedNodeId": "evt-uuid", "name": "OrderCreated", "description": "..."},
            "testCases": [
                {
                    "scenarioDescription": "Create order with valid items",
                    "givenFieldValues": {"orderId": "ORD-001"},
                    "whenFieldValues": {"items": "[...]", "customerId": "CUST-001"},
                    "thenFieldValues": {"orderId": "ORD-001", "status": "PENDING"}
                }
            ]
        }
    ]
}
```

---

## PRD 생성 함수 및 아티팩트

### 1. 메인 PRD 생성 (`generate_main_prd`)

**위치**: `api/features/prd_generation/prd_artifact_generation.py`

**생성 내용**:
- 프로젝트 이름 및 생성 시간
- 기술 스택 테이블 (Language, Framework, Messaging, Database, Deployment)
- Bounded Context 요약 테이블 (Aggregate, Command, Event, ReadModel, Policy, UI 개수)

**예시**:
```markdown
# my-project - Product Requirements Document

Generated: 2024-01-15 10:30:00

## Technology Stack

| Component | Choice |
|-----------|--------|
| **Language** | java |
| **Framework** | spring-boot |
| **Messaging** | kafka |
| **Database** | postgresql |
| **Deployment** | microservices |

## Bounded Contexts

| BC Name | Aggregates | Commands | Events | ReadModels | Policies | UIs |
|---------|------------|----------|--------|------------|----------|-----|
| Order Management | 2 | 5 | 8 | 3 | 2 | 4 |
```

### 2. BC별 상세 스펙 생성 (`generate_bc_spec`)

**생성 내용**:
- BC 개요 (ID, Description)
- **Aggregates**:
  - Root Entity
  - **Invariants**: 비즈니스 불변식 목록
  - **Enumerations**: 열거형 타입 목록
  - **Value Objects**: 값 객체 목록
  - Properties (타입, Key 여부, Foreign Key 여부, fkTargetHint)
  - Commands (Actor, Category, InputSchema, Description, Properties)
  - Events (Version, Schema, Description, Properties)
- **ReadModels**: 이름, 설명, Provisioning Type, Actor, isMultipleResult, Properties
- **Policies**: 이름, 설명, Trigger Event (Cross-BC 정보 포함), Invoke Command (Cross-BC 정보 포함)
- **UI Wireframes**: 이름, 설명, 연결된 Command/ReadModel
- **GWT Test Cases**: Given/When/Then 구조 및 상세 테스트 시나리오 (scenarioDescription, givenFieldValues, whenFieldValues, thenFieldValues)
- Implementation Notes (Framework, Messaging)

**예시**:
```markdown
# Order Management Bounded Context Specification

## Overview
- **BC ID**: bc-123
- **Description**: 주문 관리 도메인

## Aggregates

### Order
- Root Entity: `Order`
- Properties:
  - `orderId`: String (Key)
  - `customerId`: String (FK -> Customer)
  - `amount`: Decimal
- Commands:
  - `CreateOrder` (actor: customer)
    - Properties:
      - `items`: Array (required)
      - `shippingAddress`: String (required)
- Events:
  - `OrderCreated` (v1.0.0)
    - Properties:
      - `orderId`: String
      - `customerId`: String
```

### 3. Claude AI 컨텍스트 (`generate_claude_md`)

**생성 내용**:
- 프로젝트 기본 정보
- Bounded Context 목록

**용도**: Claude AI가 프로젝트 컨텍스트를 이해하는 데 사용

### 4. Cursor IDE 규칙 (`generate_cursor_rules`)

**생성 내용**:
- DDD 네이밍 규칙
- BC 경계 유지 원칙
- Event/Command 스키마 명시성 원칙

**용도**: Cursor IDE의 AI 어시스턴트가 코드 생성 시 따라야 할 규칙

### 5. BC별 AI 어시스턴트 설정

#### Cursor 규칙 (`generate_cursor_rule`) - `ai_assistant=cursor`일 때
- **파일 위치**: `.cursor/rules/{bc_name}.mdc`
- **형식**: Cursor `.mdc` 형식 (frontmatter 포함)
- **생성 내용**:
  - BC별 스코프 제한 (해당 BC 폴더만 수정)
  - Aggregates, Commands, Events, ReadModels, Policies별 구현 가이드
  - 기술 스택별 구현 가이드
  - Cross-BC 통신 규칙
  - 테스트 요구사항
  - 파일 참조는 `[filename](mdc:filename)` 형식

#### Claude 에이전트 설정 (`generate_agent_config`) - `ai_assistant=claude`일 때
- **파일 위치**: `.claude/agents/{bc_name}_agent.md`
- **형식**: Markdown
- **생성 내용**:
  - BC별 스코프 제한 (해당 BC 폴더만 수정)
  - Aggregates, Commands, Events, ReadModels, Policies별 구현 가이드
  - 기술 스택별 구현 가이드
  - Cross-BC 통신 규칙
  - 테스트 요구사항

**용도**: AI 에이전트가 특정 BC에만 집중하도록 제한하고 구현 가이드 제공

### 6. README 생성 (`generate_readme`)

**생성 내용**:
- 프로젝트 이름
- Bounded Context 목록 및 설명

### 7. Docker 파일 생성 (선택적)

**조건**: `config.include_docker == True`

- **Dockerfile**: Framework에 따라 다른 템플릿 (FastAPI, NestJS/Express, 기타)
- **docker-compose.yml**: Database에 따라 다른 서비스 (PostgreSQL, MongoDB)

---

## API 엔드포인트

### 1. PRD 생성 계획 조회

**엔드포인트**: `POST /api/prd/generate`

**요청**:
```json
{
  "node_ids": ["node-id-1", "node-id-2"],  // 선택적, null이면 전체 BC
  "tech_stack": {
    "language": "java",
    "framework": "spring-boot",
    "messaging": "kafka",
    "deployment": "microservices",
    "database": "postgresql",
    "project_name": "my-project",
    "package_name": "com.example",
    "include_docker": true,
    "include_kubernetes": false,
    "include_tests": true,
    "ai_assistant": "cursor"  // "cursor" 또는 "claude" (기본값: "cursor")
  }
}
```

**응답**:
```json
{
  "success": true,
  "bounded_contexts": [
    {"id": "bc-123", "name": "Order Management"}
  ],
  "tech_stack": {...},
  "files_to_generate": [
    "CLAUDE.md",
    "PRD.md",
    ".cursorrules",
    "specs/order_management_spec.md",
    ".cursor/rules/order_management.mdc",  // ai_assistant=cursor일 때
    // 또는 ".claude/agents/order_management_agent.md",  // ai_assistant=claude일 때
    "docker-compose.yml",
    "Dockerfile",
    "README.md"
  ],
  "download_url": "/api/prd/download"
}
```

### 2. PRD ZIP 다운로드

**엔드포인트**: `POST /api/prd/download`

**요청**: `PRDGenerationRequest` (동일)

**응답**: ZIP 파일 스트림
- Content-Type: `application/zip`
- 파일명: `{project_name}_prd_{timestamp}.zip`

### 3. 기술 스택 목록 조회

**엔드포인트**: `GET /api/prd/tech-stacks`

**응답**: 사용 가능한 Language, Framework, Messaging, Database, Deployment 옵션 목록

---

## 생성되는 파일 구조

```
{project_name}_prd_{timestamp}.zip
├── CLAUDE.md                          # Claude AI 컨텍스트
├── PRD.md                             # 메인 PRD 문서
├── .cursorrules                       # Cursor IDE 전역 규칙
├── README.md                          # 프로젝트 개요
├── specs/                             # BC별 상세 스펙
│   ├── order_management_spec.md
│   ├── payment_processing_spec.md
│   └── ...
├── .cursor/                           # Cursor 규칙 (ai_assistant=cursor일 때)
│   └── rules/
│       ├── order_management.mdc
│       ├── payment_processing.mdc
│       └── ...
├── .claude/                           # Claude 에이전트 설정 (ai_assistant=claude일 때)
│   └── agents/
│       ├── order_management_agent.md
│       ├── payment_processing_agent.md
│       └── ...
├── docker-compose.yml                 # Docker Compose (선택적)
└── Dockerfile                         # Dockerfile (선택적)
```

**참고**: `.cursor/rules/` 또는 `.claude/agents/` 중 하나만 생성됩니다 (ai_assistant 설정에 따라).

---

## 기술 스택 설정

### TechStackConfig 구조

```python
class TechStackConfig:
    language: Language          # java, kotlin, typescript, python, go
    framework: Framework        # spring-boot, spring-webflux, nestjs, express, fastapi, gin, fiber
    messaging: MessagingPlatform # kafka, rabbitmq, redis-streams, pulsar, in-memory
    deployment: DeploymentStyle  # microservices, modular-monolith
    database: Database          # postgresql, mysql, mongodb, h2
    project_name: str           # 프로젝트 이름
    package_name: str           # 패키지 이름 (Java/Kotlin용)
    include_docker: bool         # Docker 파일 포함 여부
    include_kubernetes: bool    # Kubernetes 설정 포함 여부 (미구현)
    include_tests: bool         # 테스트 포함 여부 (미구현)
    ai_assistant: AIAssistant    # cursor 또는 claude (기본값: cursor)
```

### AI Assistant 선택

`ai_assistant` 필드를 통해 사용할 AI 어시스턴트를 선택할 수 있습니다:

- **`cursor`** (기본값): Cursor IDE용 규칙 파일 생성
  - `.cursor/rules/{bc_name}.mdc` 형식으로 BC별 규칙 생성
  - Cursor의 `.mdc` 형식 (frontmatter 포함)
  - 파일 참조는 `[filename](mdc:filename)` 형식 사용
  
- **`claude`**: Claude Code용 에이전트 설정 생성
  - `.claude/agents/{bc_name}_agent.md` 형식으로 BC별 에이전트 설정 생성
  - Claude Code의 표준 형식

**참고**: `.cursorrules` 파일은 항상 생성됩니다 (전역 Cursor 규칙).

### 기술 스택이 PRD에 미치는 영향

1. **Technology Stack 테이블**: PRD.md에 기술 선택 사항 표시
2. **Implementation Notes**: BC 스펙에 Framework, Messaging 정보 포함
3. **Docker 파일**: Framework와 Database에 따라 다른 템플릿 사용
4. **에이전트 설정**: Language/Framework에 맞는 코딩 규칙 제안

---

## 데이터 흐름 다이어그램

```
┌─────────────────┐
│  사용자 요청     │
│  (node_ids)     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ get_bcs_from_   │
│ nodes()         │
│                 │
│ 1. 노드 ID 해석  │
│ 2. BC ID 추출    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ fetch_bc_data() │
│ (각 BC별)       │
│                 │
│ Neo4j Cypher    │
│ 쿼리 실행        │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ BC 데이터 구조  │
│ (dict 리스트)    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 아티팩트 생성    │
│                 │
│ • generate_main_│
│   prd()         │
│ • generate_bc_  │
│   spec()        │
│ • generate_     │
│   claude_md()   │
│ • ...           │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ ZIP 패키징      │
│                 │
│ zipfile.ZipFile │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 스트림 응답     │
│ (ZIP 파일)      │
└─────────────────┘
```

---

## 주요 파일 위치

### 백엔드 코드

- **API 라우터**: `api/features/prd_generation/router.py`
- **엔드포인트**: `api/features/prd_generation/routes/prd_export.py`
- **데이터 조회**: `api/features/prd_generation/prd_model_data.py`
- **아티팩트 생성**: `api/features/prd_generation/prd_artifact_generation.py`
- **API 계약**: `api/features/prd_generation/prd_api_contracts.py`

### 관련 문서

- **도메인 모델**: `docs/DOMAIN_MODEL_FOR_ARROWS.md`
- **이벤트 스토밍 워크플로우**: `api/features/ingestion/event_storming/`

---

## 코드 생성 완전성

### Cursor IDE 바이브 코딩을 위한 정보 포함 현황

PRD 생성 시 다음 정보들이 모두 포함되어 Cursor IDE에서 완전한 애플리케이션 코드를 생성할 수 있습니다:

#### ✅ 포함된 정보

1. **Aggregate 정보**:
   - ✅ Root Entity
   - ✅ Properties (타입, Key, Foreign Key, fkTargetHint)
   - ✅ Invariants (비즈니스 불변식)
   - ✅ Enumerations (열거형 타입)
   - ✅ Value Objects (값 객체)

2. **Command 정보**:
   - ✅ Name, Actor, Category
   - ✅ InputSchema (JSON 스키마)
   - ✅ Description
   - ✅ Properties (타입, Required 여부)

3. **Event 정보**:
   - ✅ Name, Version
   - ✅ Schema (JSON 스키마)
   - ✅ Description
   - ✅ Properties (타입)

4. **ReadModel 정보**:
   - ✅ Name, Description
   - ✅ Provisioning Type (CQRS)
   - ✅ Actor
   - ✅ isMultipleResult (list/collection/single result)
   - ✅ Properties (타입)

5. **Policy 정보**:
   - ✅ Name, Description
   - ✅ Trigger Event (이름, BC 정보)
   - ✅ Invoke Command (이름, BC 정보)
   - ✅ Cross-BC 통신 정보

6. **GWT Test Cases**:
   - ✅ Given/When/Then 구조
   - ✅ Test Scenarios (scenarioDescription)
   - ✅ Field Values (givenFieldValues, whenFieldValues, thenFieldValues)

7. **기술 스택 정보**:
   - ✅ Language, Framework, Messaging, Database, Deployment
   - ✅ Implementation Notes

#### 코드 생성에 활용 가능한 정보

이러한 정보들을 바탕으로 Cursor IDE는 다음을 생성할 수 있습니다:

1. **Aggregate 엔티티 클래스**: Root Entity, Properties, Invariants, Enumerations, Value Objects
2. **Command 핸들러**: InputSchema 기반 DTO, Validation 로직, Actor 기반 권한 체크
3. **Event 클래스**: Schema 기반 Event 정의, Version 관리
4. **ReadModel 프로젝션**: Actor 기반 쿼리, isMultipleResult 기반 반환 타입
5. **Policy 구현**: Cross-BC Event/Command 통신, 메시징 플랫폼 통합
6. **테스트 코드**: GWT 시나리오 기반 Given/When/Then 테스트
7. **API 엔드포인트**: Framework 기반 REST API 생성
8. **데이터베이스 스키마**: Properties 기반 DDL 생성

## 확장 가능성

### 향후 개선 사항

1. **테스트 코드 생성**: `include_tests: true`일 때 GWT 기반 테스트 코드 생성
2. **Kubernetes 설정**: `include_kubernetes: true`일 때 K8s 매니페스트 생성
3. **코드 스켈레톤 생성**: PRD 기반 실제 프로젝트 코드 생성
4. **API 스펙 생성**: OpenAPI/Swagger 스펙 자동 생성
5. **데이터베이스 스키마 생성**: Aggregate Properties 기반 DDL 생성

---

## 참고사항

### 노드 ID 해석의 중요성

- 사용자가 Canvas에서 특정 노드(Command, Event 등)를 선택해도, 시스템은 자동으로 해당 노드가 속한 Bounded Context를 찾아 전체 BC 데이터를 조회합니다.
- 이를 통해 BC의 전체 맥락을 포함한 PRD를 생성할 수 있습니다.

### 데이터 일관성

- Neo4j 그래프의 관계를 통해 모든 데이터가 연결되어 있습니다.
- Property의 `isForeignKey` 및 `fkTargetHint`를 통해 Aggregate 간 관계를 파악할 수 있습니다.

### 추적성(Traceability)

- User Story → Command → Event 간의 `user_story_ids` 추적이 가능합니다.
- 이를 통해 요구사항 변경 시 영향 범위를 파악할 수 있습니다.

---

## 예제 시나리오

### 시나리오 1: 전체 PRD 생성

```bash
POST /api/prd/generate
{
  "node_ids": null,
  "tech_stack": {
    "language": "java",
    "framework": "spring-boot",
    "messaging": "kafka",
    "deployment": "microservices",
    "database": "postgresql",
    "project_name": "ecommerce-platform",
    "include_docker": true
  }
}
```

**결과**: 모든 Bounded Context를 포함한 전체 PRD 생성

### 시나리오 2: 특정 BC만 포함

```bash
POST /api/prd/generate
{
  "node_ids": ["cmd-create-order"],
  "tech_stack": {...}
}
```

**결과**: `CreateOrder` Command가 속한 Bounded Context만 포함한 PRD 생성

---

## 결론

이벤트 스토밍 모델 기반 PRD 생성은 다음과 같은 특징을 가집니다:

1. **자동화**: Neo4j 그래프에서 자동으로 데이터 추출 및 문서 생성
2. **맥락 보존**: BC 단위로 전체 도메인 맥락을 포함
3. **AI 친화적**: Claude, Cursor 등 AI 도구를 위한 컨텍스트 파일 자동 생성
4. **확장 가능**: 기술 스택 설정에 따라 다양한 아티팩트 생성 가능
5. **추적 가능**: User Story부터 구현까지의 추적성 유지

이를 통해 Event Storming으로 설계한 도메인 모델을 실제 개발에 바로 활용할 수 있는 문서와 컨텍스트를 제공합니다.
