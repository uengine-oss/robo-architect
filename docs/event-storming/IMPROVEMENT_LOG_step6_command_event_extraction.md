# Step 6: Command/Event 추출 개선 - 개선 로그

## 개선 목표
Event Storming 워크플로우의 Command 및 Event 추출 단계에서 backend-generators의 노하우를 활용하여 더 정확하고 구조화된 Command/Event 추출을 구현합니다. 상세한 프롬프트 구조, Event Discovery Methodology 적용, 그리고 향후 대용량 처리(청킹)를 위한 기반을 마련합니다.

---

## 참고한 backend-generators 코드

### 1. `command_readmodel_extractor.py` - Command 추출 부분만 참고
**위치**: `backend-generators/src/project_generator/workflows/sitemap/command_readmodel_extractor.py`

**참고한 내용 (Command 부분만):**
- XML 기반 상세 프롬프트 구조 (`<instruction>`, `<core_instructions>`, `<guidelines>`, `<section>`)
- **Command 추출 규칙만 참고** (State-Changing Operations, Business Processes, External System Integration)
  - `<section id="command_extraction">` 섹션만 사용
  - `<section id="readmodel_extraction">` 섹션은 제외 (ReadModel 추출 단계에서 사용 예정)
- Actor 분류 (user, admin, system, external) - Command용만
- 명명 규칙 (Verb + Noun 패턴) - Command용만
- Quality Standards 중 Command 관련 부분만

**제외한 내용:**
- ReadModel 추출 규칙 (`<section id="readmodel_extraction">`) - ReadModel 추출 단계에서 별도로 사용 예정
- ReadModel 관련 명명 규칙 (Noun + Purpose 패턴)
- ReadModel 관련 Actor 분류 (user, admin, system - external 제외)
- Bounded Context 할당 전략 중 ReadModel 관련 부분

**적용 사항:**
- Command 추출 프롬프트를 XML 구조로 재구성
- Command 카테고리화 (Create, Update, Delete, Process, Business Logic, External Integration)
- 상세한 가이드라인 및 예제 추가
- Actor 생성 로직 개선 (User Story의 role 기반, 자연스러운 도메인 적합한 actor 이름 사용)

### 2. `requirements_validator.py` - Event Discovery Methodology
**위치**: `backend-generators/src/project_generator/workflows/requirements_validation/requirements_validator.py`

**참고한 내용:**
- Event Discovery Methodology:
  - Comprehensive Coverage: 모든 중요한 비즈니스 순간을 도메인 이벤트로 변환
  - Complete State Capture: 모든 비즈니스적으로 중요한 상태 변경을 이벤트로 표현
  - Flow Completeness: Happy path와 예외 흐름 모두 포함
  - State Change Focus: 비즈니스적으로 중요한 상태 변경만 이벤트화
  - Primary Business Actions: 주요 비즈니스 액션에 집중
- Event 명명 규칙 (PascalCase, Past Participle)
- Source Traceability (refs) 처리

**적용 사항:**
- Event Discovery Methodology를 Event 추출 프롬프트에 통합
- Event 카테고리화 (Creation, State Change, Completion, Failure, Business Process)
- 명명 규칙 강화 (Noun + Past Participle)
- Command-Event 매핑 규칙 명확화

### 3. `command_readmodel_extractor.py` - 청킹 처리
**위치**: `backend-generators/src/project_generator/workflows/sitemap/command_readmodel_extractor.py` (라인 27-49, 82-104)

**참고한 내용:**
- `split_requirements_into_chunks()` 함수: 문장 단위로 청크 분할
- 청크 크기 결정 로직 (기본 12000자)
- 청크별 순차 처리 및 결과 병합
- 중복 제거 로직

**적용 사항:**
- 향후 대용량 User Story 처리 시 청킹 로직 적용 예정
- 현재는 프롬프트 강화에 집중, 청킹은 필요 시 추가

---

## 구현 내용

### 1. Command 추출 프롬프트 강화

#### Before (기존)
```python
EXTRACT_COMMANDS_PROMPT = """Identify Commands for the given Aggregate based on user story requirements.

Aggregate: {aggregate_name}
Aggregate ID: {aggregate_id}
Bounded Context: {bc_name}

User Stories for this Aggregate:
{user_story_context}

Guidelines for identifying Commands:
1. Commands represent user/system intentions to change state
2. Name commands as imperative verbs (CreateOrder, CancelOrder)
3. Each command should map to a user action or system trigger
4. Commands are handled by exactly one aggregate
5. IMPORTANT: Track which user story each command implements

For each Command, provide:
- The command name in PascalCase
- Who/what triggers this command (user, system, policy)
- A description of what the command does
- user_story_ids: List of User Story IDs that this command directly implements

Example:
- PlaceOrder: implements [US-001]
- CancelOrder: implements [US-002]

This creates traceability: UserStory -> Command

Output should be a list of CommandCandidate objects."""
```

#### After (개선 후)
```python
EXTRACT_COMMANDS_PROMPT = """You are tasked with identifying Commands for the given Aggregate based on User Story requirements, following Domain-Driven Design and Event Storming principles.

<target_aggregate>
Name: {aggregate_name}
ID: {aggregate_id}
Bounded Context: {bc_name}
</target_aggregate>

<user_stories>
{user_story_context}
</user_stories>

<core_instructions>
<title>Command Identification Task</title>
<task_description>...</task_description>

<guidelines>
<title>Command Identification Guidelines</title>

<section id="command_definition">
<title>What is a Command?</title>
<rule id="1">**State-Changing Intent:** ...</rule>
<rule id="2">**Single Aggregate Responsibility:** ...</rule>
...
</section>

<section id="command_categories">
<title>Command Categories</title>
<rule id="1">
<name>Create Operations</name>
<description>...</description>
<examples>CreateOrder, RegisterUser, CreateReservation</examples>
</rule>
...
</section>

<section id="naming_conventions">
<title>Naming Conventions</title>
<rule id="1">**Verb + Noun Pattern:** ...</rule>
...
</section>

<section id="actor_classification">
<title>Actor Classification</title>
<rule id="1">**user:** Commands triggered by end users...</rule>
<rule id="2">**admin:** Commands triggered by administrators...</rule>
<rule id="3">**system:** Commands triggered by system processes...</rule>
<rule id="4">**external:** Commands triggered by external systems...</rule>
</section>

<section id="traceability">
<title>Traceability Requirements</title>
<rule id="1">**User Story Mapping:** ...</rule>
...
</section>

<section id="command_event_relationship">
<title>Command-Event Relationship</title>
<rule id="1">**Event Emission:** Every Command should emit at least one Event...</rule>
...
</section>
</guidelines>
</core_instructions>

<analysis_approach>
...
</analysis_approach>

<output_requirements>
...
</output_requirements>

<examples>
...
</examples>
"""
```

### 2. Event 추출 프롬프트 강화

#### Before (기존)
```python
EXTRACT_EVENTS_PROMPT = """Identify Events emitted by Commands in this Aggregate.

Aggregate: {aggregate_name}
Bounded Context: {bc_name}
Commands (with their user stories):
{commands}

Guidelines for identifying Events:
1. Events represent facts that happened (past tense)
2. Name events as NounPastVerb (OrderCreated, PaymentProcessed)
3. Every command should emit at least one event on success
4. Events are immutable facts - they cannot be changed
5. IMPORTANT: Inherit user_story_ids from the command that emits this event

For each Event, provide:
- The event name in PascalCase
- A description of what happened
- user_story_ids: List of User Story IDs (inherited from the emitting command)

Example:
- OrderPlaced: implements [US-001]
- OrderCancelled: implements [US-002]

This creates traceability: UserStory -> Command -> Event

Output should be a list of EventCandidate objects."""
```

#### After (개선 후)
```python
EXTRACT_EVENTS_PROMPT = """You are tasked with identifying Events emitted by Commands in this Aggregate, following Domain-Driven Design and Event Storming principles.

<target_aggregate>
Name: {aggregate_name}
Bounded Context: {bc_name}
</target_aggregate>

<commands>
{commands}
</commands>

<core_instructions>
<title>Event Identification Task</title>
<task_description>...</task_description>

<guidelines>
<title>Event Identification Guidelines</title>

<section id="event_definition">
<title>What is an Event?</title>
<rule id="1">**Immutable Facts:** Events represent facts that have already happened...</rule>
<rule id="2">**Past Tense:** Events are named in past tense...</rule>
...
</section>

<section id="event_discovery_methodology">
<title>Event Discovery Methodology</title>
<rule id="1">
<name>Comprehensive Coverage</name>
<description>Convert EVERY significant business moment into domain events...</description>
</rule>
<rule id="2">
<name>Complete State Capture</name>
<description>Ensure ALL business-significant state changes are represented as events...</description>
</rule>
<rule id="3">
<name>Flow Completeness</name>
<description>Include both happy path scenarios AND exception flows...</description>
</rule>
<rule id="4">
<name>State Change Focus</name>
<description>Generate events ONLY for business-significant state changes...</description>
</rule>
<rule id="5">
<name>Primary Business Actions</name>
<description>Focus on the primary business action rather than secondary consequences...</description>
</rule>
</section>

<section id="event_categories">
<title>Event Categories</title>
<rule id="1">
<name>Creation Events</name>
<description>Events emitted when new entities are created</description>
<examples>OrderCreated, UserRegistered, ReservationMade</examples>
</rule>
...
</section>

<section id="naming_conventions">
<title>Naming Conventions</title>
<rule id="1">**Past Participle Pattern:** Use Noun + Past Participle in PascalCase...</rule>
...
</section>

<section id="command_event_mapping">
<title>Command-Event Mapping</title>
<rule id="1">**One-to-Many Relationship:** A Command can emit multiple Events...</rule>
...
</section>

<section id="traceability">
<title>Traceability Requirements</title>
<rule id="1">**User Story Inheritance:** Events MUST inherit user_story_ids...</rule>
...
</section>

<section id="event_versioning">
<title>Event Versioning</title>
<rule id="1">**Version Format:** Events use semantic versioning...</rule>
...
</section>
</guidelines>
</core_instructions>

<analysis_approach>
...
</analysis_approach>

<output_requirements>
...
</output_requirements>

<examples>
...
</examples>
"""
```

### 3. Command 추출 가이드라인 추가

#### Command Definition
- **State-Changing Intent:** Commands represent intentions to change the system's state
- **Single Aggregate Responsibility:** Each Command is handled by exactly ONE Aggregate
- **User/System Intent:** Commands can be triggered by users, systems, or policies
- **Idempotency Consideration:** Some commands may be idempotent

#### Command Categories
1. **Create Operations:** CreateOrder, RegisterUser, CreateReservation
2. **Update Operations:** UpdateProfile, ModifyOrder, ChangeReservationStatus
3. **Delete/Cancel Operations:** CancelOrder, DeleteReservation, RemoveItem
4. **Process Operations:** ProcessPayment, ConfirmReservation, VerifyEmail
5. **Business Logic Operations:** ValidateOrder, AuthenticateUser, CheckAvailability
6. **External Integration Operations:** SyncInventory, NotifyExternalSystem, ImportData

#### Actor Classification
- **user:** Commands triggered by end users through UI or API
- **admin:** Commands triggered by administrators or privileged users
- **system:** Commands triggered by system processes, scheduled jobs, or internal workflows
- **external:** Commands triggered by external systems or services

#### Naming Conventions
- **Verb + Noun Pattern:** Use imperative verb followed by noun in PascalCase
- **Clear Intent:** Command names should clearly express the business intent
- **Domain Language:** Use domain-specific terminology
- **Avoid Generic CRUD:** Focus on domain-specific operations

### 4. Event 추출 가이드라인 추가

#### Event Discovery Methodology
1. **Comprehensive Coverage:** Convert EVERY significant business moment into domain events
2. **Complete State Capture:** Ensure ALL business-significant state changes are represented as events
3. **Flow Completeness:** Include both happy path scenarios AND exception flows
4. **State Change Focus:** Generate events ONLY for business-significant state changes
5. **Primary Business Actions:** Focus on the primary business action rather than secondary consequences

#### Event Categories
1. **Creation Events:** OrderCreated, UserRegistered, ReservationMade
2. **State Change Events:** OrderConfirmed, PaymentProcessed, ReservationCancelled
3. **Completion Events:** OrderShipped, PaymentCompleted, ReservationConfirmed
4. **Failure Events:** OrderPlacementFailed, PaymentRejected, ReservationConflictDetected
5. **Business Process Events:** OrderValidated, PaymentAuthorized, InventoryReserved

#### Naming Conventions
- **Past Participle Pattern:** Use Noun + Past Participle in PascalCase (e.g., OrderPlaced, PaymentProcessed)
- **Clear Business Intent:** Event names should clearly express what business fact occurred
- **Domain Language:** Use domain-specific terminology
- **Consistency:** Maintain consistent naming patterns across related events

#### Command-Event Mapping
- **One-to-Many Relationship:** A Command can emit multiple Events if it triggers multiple business outcomes
- **At Least One Event:** Every Command MUST emit at least one Event on successful execution
- **Event Naming Relationship:** Events are named in past tense while Commands are imperative
- **Failure Events:** Consider emitting failure events for important error scenarios

---

## 개선 효과

### Before (기존)
- 단순한 Command/Event 추출 가이드라인
- 기본적인 명명 규칙만 제공
- Actor 분류가 단순함 (user, system, policy)
- Event Discovery Methodology 없음
- 카테고리화 및 예제 부족
- Command-Event 관계 설명 부족

### After (개선 후)
- 구조화된 XML 기반 프롬프트 (가독성 및 구조화 향상)
- 상세한 Command 카테고리화 (6가지 카테고리)
- 자연스러운 Actor 생성 (User Story의 role 기반, 도메인 적합한 actor 이름 사용)
- Event Discovery Methodology 적용 (5가지 원칙)
- 상세한 Event 카테고리화 (5가지 카테고리)
- Command-Event 매핑 규칙 명확화
- 명명 규칙 강화 및 예제 추가
- Traceability 요구사항 강화
- Analysis Approach 제공 (LLM 분석 가이드)

---

## 참고 사항

### Event Storming vs backend-generators 차이점

**backend-generators의 경우:**
- 요구사항 문서에서 직접 Command/ReadModel 추출 (한 번에 함께 추출)
- 청킹 처리 필수 (대용량 요구사항)
- Bounded Context 할당 전략 포함 (Command와 ReadModel 모두)
- ReadModel 추출도 함께 수행
- Source Traceability (refs) 처리

**Event Storming의 경우:**
- User Story 기반 Command 추출 (이미 BC와 Aggregate가 정의됨)
- Command 기반 Event 추출 (Command → Event 순서)
- 청킹은 필요 시 추가 (현재는 프롬프트 강화에 집중)
- **ReadModel은 별도 단계에서 처리** (Command 추출과 분리)
- Traceability는 user_story_ids를 통해 관리

**중요:** `command_readmodel_extractor.py`에서 **Command 추출 부분만** 참고했으며, ReadModel 관련 내용은 제외했습니다. ReadModel 추출은 Event Storming 워크플로우에서 별도 단계로 처리되므로, 해당 단계에서 ReadModel 관련 노하우를 적용할 예정입니다.

따라서 backend-generators의 모든 기능을 그대로 적용하기보다는, Event Storming의 컨텍스트에 맞게 조정하여 적용했습니다.

### 추가 개선 사항 (2024년 적용)

#### 1. Command/Event 메타데이터 저장 및 활용
- **목적**: Property 생성 시 Command의 inputSchema와 Event의 payload를 참고하여 더 정확한 Properties 생성
- **구현**:
  - Command 생성 시 `category`, `inputSchema` 저장
  - Event 생성 시 `version`, `payload` 저장
  - Property 생성 프롬프트에 이 정보들을 포함하여 LLM이 참고하도록 지시
- **효과**: backend-generators의 원래 워크플로우와 유사하게, Command/Event 생성 시 생성된 스키마 정보를 Property 생성 시 활용 가능

#### 2. Actor 생성 로직 개선
- **목적**: User Story의 role에 맞게 자연스러운 actor 생성
- **구현**:
  - 기존: 4가지 고정 카테고리 (user, admin, system, external)만 사용
  - 개선: User Story의 role을 우선 사용, 자연스러운 도메인 적합한 actor 이름 사용
  - 예: "customer", "seller", "delivery_driver", "warehouse_manager" 등
- **효과**: 더 정확하고 도메인에 맞는 actor 분류

### 향후 개선 가능 사항

1. **대용량 처리 (청킹)**
   - User Story가 대용량일 경우 청크로 분할
   - 각 청크별 Command/Event 추출
   - 결과 병합 및 중복 제거
   - `split_requirements_into_chunks()` 패턴 활용

2. **Source Traceability 강화**
   - Requirements line number 참조 (현재는 user_story_ids만 사용)
   - Event refs 변환 로직 추가 (requirements_validator 패턴)

3. **Command-Event 매핑 검증**
   - 모든 Command가 Event를 emit하는지 확인
   - Event가 적절한 Command에서 발생하는지 검증
   - Event 체인 완전성 검증

4. **RAG 기반 패턴 검색**
   - Knowledge base에서 유사 Command/Event 패턴 검색
   - 도메인별 모범 사례 제공

### 제외된 기능 (의도적으로)

**ReadModel 추출:**
- Event Storming 워크플로우에는 **ReadModel 추출** 단계가 별도로 존재
- Command/Event 추출과는 분리되어 처리
- 따라서 Command 추출 프롬프트에 ReadModel 관련 내용은 제외
- `command_readmodel_extractor.py`의 `<section id="readmodel_extraction">` 섹션은 ReadModel 추출 단계에서 별도로 활용 예정

**Property Generation:**
- Event Storming 워크플로우에는 이미 **Property Generation (Phase 1)** 단계가 별도로 존재
- Command, Event가 모두 생성된 후 별도 단계에서 필드 생성
- 따라서 Command/Event 추출 단계에서 필드 생성은 중복이며 불필요

**Command/Event 추출 단계의 역할:**
- Command 구조 정의 (name, actor, description)
- Event 구조 정의 (name, description)
- User Story 매핑 (traceability)
- Command-Event 관계 설정
- 필드 생성은 Property Generation 단계에서 처리

---

## 테스트 시나리오

### 1. 정상 케이스
- User Story에서 명확한 Command가 식별되는 경우
- Command에서 적절한 Event가 추출되는 경우
- 모든 User Story가 Command에 매핑되는 경우
- Command-Event 매핑이 올바른 경우

### 2. 경계 케이스
- Command 경계가 모호한 경우
- Event가 필요한지 불명확한 경우
- User Story가 여러 Command에 걸치는 경우
- Command가 여러 Event를 emit해야 하는 경우

### 3. 검증 케이스
- 모든 User Story가 Command에 할당되었는지 확인
- 모든 Command가 Event를 emit하는지 확인
- Command 이름이 Verb+Noun 패턴인지 확인
- Event 이름이 Noun+PastParticiple 패턴인지 확인
- Actor가 User Story의 role과 일치하거나 도메인에 적합한지 확인
- user_story_ids traceability가 올바른지 확인

---

## 참고 파일

### 수정된 파일
- `api/features/ingestion/event_storming/prompts.py`
  - `EXTRACT_COMMANDS_PROMPT` 프롬프트 강화 (XML 구조, 상세 가이드라인, 예제 추가)
  - `EXTRACT_EVENTS_PROMPT` 프롬프트 강화 (Event Discovery Methodology 적용)
  - `GENERATE_PROPERTIES_AGGREGATE_BATCH_PROMPT` 프롬프트 업데이트 (Command의 inputSchema, Event의 payload 참고 지시 추가)

- `api/features/ingestion/event_storming/state.py`
  - `CommandCandidate` 모델에 `category`, `inputSchema` 필드 추가
  - `EventCandidate` 모델에 `version`, `payload` 필드 추가

- `api/features/ingestion/event_storming/neo4j_ops/commands.py`
  - `create_command` 함수에 `category` 파라미터 추가 및 저장 로직 수정

- `api/features/ingestion/event_storming/neo4j_ops/events.py`
  - `create_event` 함수에 `payload` 파라미터 추가 및 저장 로직 수정

- `api/features/ingestion/event_storming/nodes_persist.py`
  - Command 생성 시 `category`, `inputSchema` 전달
  - Event 생성 시 `version`, `payload` 전달

- `api/features/ingestion/workflow/phases/commands.py`
  - Command 생성 시 `category`, `inputSchema`를 Neo4j에 저장하도록 수정

- `api/features/ingestion/workflow/phases/events.py`
  - Event 생성 시 `version`, `payload`를 Neo4j에 저장하도록 수정

- `api/features/ingestion/workflow/phases/properties.py`
  - Property 생성 프롬프트에 Command의 `category`, `inputSchema` 포함
  - Property 생성 프롬프트에 Event의 `version`, `payload` 포함

- `api/features/contexts/router.py`
  - `get_context_full_tree` API에서 Command의 `category` 반환
  - `get_context_full_tree` API에서 Event의 `payload` 반환

### 참고한 backend-generators 파일
- `backend-generators/src/project_generator/workflows/sitemap/command_readmodel_extractor.py`
  - **Command 추출 부분만 참고:**
    - `<section id="command_extraction">` 섹션 (라인 253-296)
    - Command 관련 명명 규칙 및 Actor 분류
    - XML 프롬프트 구조 패턴
  - **제외한 부분:**
    - `<section id="readmodel_extraction">` 섹션 (라인 298-352) - ReadModel 추출 단계에서 별도 활용 예정
    - ReadModel 관련 명명 규칙 및 Actor 분류
  - 청킹 처리 로직 (라인 27-49, 82-104) - 향후 적용 예정
  - `split_requirements_into_chunks()` 함수 - 향후 적용 예정
  - `merge_extracted_data()` 함수 - 향후 적용 예정

- `backend-generators/src/project_generator/workflows/requirements_validation/requirements_validator.py`
  - Event Discovery Methodology (라인 131-138)
  - Event 명명 규칙 및 가이드라인
  - Source Traceability (refs) 처리 로직

### 향후 수정 예정 파일
- `api/features/ingestion/event_storming/nodes_commands.py`
  - 대용량 처리 로직 추가 (청킹, 필요 시)
  
- `api/features/ingestion/event_storming/nodes_events.py`
  - 대용량 처리 로직 추가 (청킹, 필요 시)

- `api/features/ingestion/workflow/phases/commands.py`
  - 대용량 처리 로직 추가 (청킹, 필요 시)

- `api/features/ingestion/workflow/phases/events.py`
  - 대용량 처리 로직 추가 (청킹, 필요 시)
