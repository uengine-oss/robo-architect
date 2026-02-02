# Step 5: Aggregate 추출 개선 - 개선 로그

## 개선 목표
Event Storming 워크플로우의 Aggregate 추출 단계에서 backend-generators의 노하우를 활용하여 더 정확하고 구조화된 Aggregate 추출을 구현합니다. Enumerations, Value Objects 식별 및 추적성 정보를 강화합니다.

---

## 참고한 backend-generators 코드

### 1. `aggregate_draft_generator.py` - 전체 구조
**위치**: `backend-generators/src/project_generator/workflows/aggregate_draft/aggregate_draft_generator.py`

**참고한 내용:**
- 여러 Aggregate 설계 옵션 생성 (2-3개)
- Pros/Cons 분석 (cohesion, coupling, consistency, encapsulation, complexity, independence, performance)
- Enumerations 및 Value Objects 식별
- 추적성 정보 관리 (traceMap)
- 복잡한 프롬프트 구조

**적용 사항:**
- AggregateCandidate 모델에 Enumerations와 Value Objects 필드 추가
- 프롬프트에 Aggregate 구조 요구사항 통합
- Enumerations 및 Value Objects 식별 가이드 추가

### 2. `aggregate_draft_generator.py` - `_get_response_schema` 메서드
**위치**: `backend-generators/src/project_generator/workflows/aggregate_draft/aggregate_draft_generator.py` (라인 60-171)

**참고한 내용:**
- Enumerations 스키마 구조 (name, alias)
- Value Objects 스키마 구조 (name, alias, referencedAggregateName)
- Aggregate 구조 내 Enumerations와 Value Objects 포함

**적용 사항:**
- `EnumerationCandidate` 모델 추가
- `ValueObjectCandidate` 모델 추가
- `AggregateCandidate`에 `enumerations`와 `value_objects` 필드 추가

### 3. `aggregate_draft_generator.py` - `_build_prompt` 메서드
**위치**: `backend-generators/src/project_generator/workflows/aggregate_draft/aggregate_draft_generator.py` (라인 378-479)

**참고한 내용:**
- Guidelines 구조 (10가지 원칙)
- Alignment with Functional Requirements and Business Rules
- Event-Driven Design Considerations
- Context Relationship Analysis
- Transactional Consistency
- Design for Maintainability
- Proper Use of Enumerations
- Naming and Language Conventions
- Reference Handling and Duplication Avoidance
- Aggregate References
- High-Quality Evaluation of Options

**적용 사항:**
- Event Storming에 맞게 조정하여 프롬프트 강화
- Core Principles, Aggregate Structure Requirements, Naming Conventions, Traceability Requirements 섹션 추가
- Analysis Approach 추가

### 4. `aggregate_draft_generator.py` - `_prepare_inputs` 메서드
**위치**: `backend-generators/src/project_generator/workflows/aggregate_draft/aggregate_draft_generator.py` (라인 190-213)

**참고한 내용:**
- Requirements 포맷팅 (`_format_requirements`)
- Context Relations 포맷팅 (`_format_context_relations`)

**적용 사항:**
- Event Storming은 User Story Breakdown을 사용하므로, Breakdown 정보를 더 효과적으로 활용하도록 프롬프트 개선

---

## 구현 내용

### 1. AggregateCandidate 모델 확장

#### Before (기존)
```python
class AggregateCandidate(BaseModel):
    id: Optional[str]
    key: Optional[str]
    name: str
    root_entity: str
    invariants: List[str]
    description: str
    user_story_ids: List[str]
```

#### After (개선 후)
```python
class EnumerationCandidate(BaseModel):
    name: str
    alias: Optional[str]

class ValueObjectCandidate(BaseModel):
    name: str
    alias: Optional[str]
    referenced_aggregate_name: Optional[str]

class AggregateCandidate(BaseModel):
    id: Optional[str]
    key: Optional[str]
    name: str
    root_entity: str
    invariants: List[str]
    description: str
    user_story_ids: List[str]
    enumerations: List[EnumerationCandidate]  # 추가
    value_objects: List[ValueObjectCandidate]  # 추가
```

### 2. 프롬프트 구조 강화

#### Before (기존)
```python
EXTRACT_AGGREGATES_PROMPT = """Based on the User Story breakdown, identify Aggregates for this Bounded Context.

Bounded Context: {bc_name} (ID: {bc_id})
Description: {bc_description}

User Story Breakdowns (ONLY for this BC):
{breakdowns}

CRITICAL RULES:
1. An Aggregate belongs to EXACTLY ONE Bounded Context
...
"""
```

#### After (개선 후)
```python
EXTRACT_AGGREGATES_PROMPT = """You are tasked with identifying Aggregates within a specified Bounded Context based on User Story breakdowns, following Domain-Driven Design principles.

<target_bounded_context>
Name: {bc_name}
ID: {bc_id}
Description: {bc_description}
</target_bounded_context>

<user_story_breakdowns>
{breakdowns}
</user_story_breakdowns>

<core_instructions>
<title>Aggregate Identification Task</title>
<task_description>...</task_description>

<guidelines>
<title>Aggregate Identification Guidelines</title>

<section id="core_principles">
<title>Core Principles</title>
<rule id="1">**Transactional Consistency:** ...</rule>
<rule id="2">**Consistency Boundaries:** ...</rule>
...
</section>

<section id="aggregate_structure">
<title>Aggregate Structure Requirements</title>
<rule id="1">**Enumerations:** When storing state or similar information, always use Enumerations...</rule>
<rule id="2">**Value Objects:** Distribute properties across well-defined Value Objects...</rule>
...
</section>

<section id="naming_conventions">
<title>Naming Conventions</title>
...
</section>

<section id="traceability">
<title>Traceability Requirements</title>
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

### 3. Core Principles 추가
- **Transactional Consistency:** 트랜잭션-중요 데이터를 단일 Aggregate 내에 통합하여 원자성 보장
- **Consistency Boundaries:** Aggregates는 일관성 경계(트랜잭션)를 강제
- **Single Bounded Context:** Aggregate는 정확히 하나의 Bounded Context에 속함
- **Aggregate Root:** 하나의 엔티티가 Aggregate Root (모든 작업의 진입점)
- **Reference by ID:** 다른 Aggregates는 ID로만 참조

### 4. Aggregate Structure Requirements 추가
- **Enumerations:** 상태나 유사한 정보를 저장할 때 항상 Enumerations 사용
- **Value Objects:** 속성을 잘 정의된 Value Objects로 분산하여 유지보수성 향상
- **Aggregate References:** 다른 Aggregates와 관련된 경우 Value Objects를 사용하여 참조 보유
- **Reference Handling:** 중복 방지를 위한 참조 처리 규칙

### 5. Naming Conventions 추가
- 영어 이름 사용
- 타입 정보 포함 금지 (예: "Book" not "BookAggregate")
- PascalCase 사용
- BC 내에서 고유성 보장

### 6. Traceability Requirements 추가
- User Story 매핑: 각 Aggregate는 구현하는 User Story IDs를 나열해야 함
- 완전한 커버리지: Breakdown에 나열된 모든 User Story가 최소 하나의 Aggregate에 의해 커버되어야 함

### 7. Analysis Approach 추가
LLM이 분석할 때 고려해야 할 사항:
- Business Invariants: 원자적으로 강제해야 하는 비즈니스 규칙
- Transactional Boundaries: 단일 트랜잭션에서 함께 변경되어야 하는 데이터
- Domain Concepts: User Story breakdown에서 언급된 주요 엔티티/개념
- Consistency Requirements: 함께 일관성을 유지해야 하는 데이터
- Potential Aggregates: Breakdown에 나열된 "Potential Aggregates" 검토

---

## 개선 효과

### Before (기존)
- 단순한 Aggregate 구조만 추출
- Enumerations 및 Value Objects 식별 없음
- Aggregate 구조에 대한 가이드 부족
- 추적성 정보가 user_story_ids만 있음

### After (개선 후)
- 구조화된 Aggregate 추출 (Enumerations, Value Objects 포함)
- Aggregate 구조 요구사항 명확화
- 명명 규칙 및 참조 처리 규칙 제공
- 추적성 정보 강화 (User Story 매핑)
- 더 상세하고 근거 있는 Aggregate 추출

---

## 참고 사항

### Event Storming vs backend-generators 차이점

**backend-generators의 경우:**
- 여러 Aggregate 설계 옵션 생성 (2-3개)
- Pros/Cons 분석 제공
- accumulated_drafts를 고려하여 중복 방지
- Context Relations 정보 활용
- traceMap을 통한 추적성 관리

**Event Storming의 경우:**
- 단일 Aggregate 후보 생성 (human-in-the-loop에서 검토)
- Pros/Cons는 선택적 (필요시 추가 가능)
- User Story Breakdown 기반 추출
- Context Relations 정보 없음 (Policy 단계에서 처리)
- user_story_ids를 통한 추적성 관리

따라서 backend-generators의 모든 기능을 그대로 적용하기보다는, Event Storming의 컨텍스트에 맞게 조정하여 적용했습니다.

### 향후 개선 가능 사항

1. **여러 Aggregate 설계 옵션 생성** (선택적)
   - backend-generators처럼 2-3개 옵션 생성
   - Pros/Cons 분석 제공
   - Human-in-the-loop에서 옵션 선택

2. **Context Relations 활용**
   - BC 간 관계 정보를 Aggregate 설계에 반영

3. **추적성 정보 강화**
   - Requirements line number 참조 (현재는 user_story_ids만 사용)
   - traceMap 형식 지원

### 제외된 기능 (의도적으로)

**DDL 기반 필드 생성 및 요구사항 기반 가상 필드 생성:**
- Event Storming 워크플로우에는 이미 **Property Generation (Phase 1)** 단계가 별도로 존재
- Aggregate, Command, Event가 모두 생성된 후 별도 단계에서 필드 생성
- 따라서 Aggregate 추출 단계에서 필드 생성은 중복이며 불필요
- backend-generators의 `ddl_extractor.py`, `ddl_fields_generator.py`, `preview_fields_generator.py`는 참고하지 않음

**Aggregate 추출 단계의 역할:**
- Aggregate 구조 정의 (name, root_entity, invariants)
- Enumerations 및 Value Objects 식별
- User Story 매핑 (traceability)
- 필드 생성은 Property Generation 단계에서 처리

---

## 테스트 시나리오

### 1. 정상 케이스
- User Story Breakdown에서 명확한 Aggregate 경계가 식별되는 경우
- Enumerations와 Value Objects가 적절히 식별되는 경우
- 모든 User Story가 Aggregate에 매핑되는 경우

### 2. 경계 케이스
- Aggregate 경계가 모호한 경우
- Enumerations나 Value Objects가 필요한지 불명확한 경우
- User Story가 여러 Aggregate에 걸치는 경우

### 3. 검증 케이스
- 모든 User Story가 Aggregate에 할당되었는지 확인
- Aggregate 이름이 PascalCase인지 확인
- Enumerations와 Value Objects가 적절히 식별되었는지 확인
- 참조 Value Objects가 올바른 Aggregate를 참조하는지 확인

---

## 참고 파일

### 수정된 파일
- `api/features/ingestion/event_storming/state.py`
  - `EnumerationCandidate` 모델 추가
  - `ValueObjectCandidate` 모델 추가
  - `AggregateCandidate` 모델 확장 (enumerations, value_objects 필드 추가)

- `api/features/ingestion/event_storming/prompts.py`
  - `EXTRACT_AGGREGATES_PROMPT` 프롬프트 강화

- `api/features/ingestion/event_storming/nodes_aggregates.py`
  - `approve_aggregates_node`: enumerations와 value_objects를 승인 화면에 표시하도록 개선

- `api/features/ingestion/event_storming/nodes_persist.py`
  - `save_to_graph_node`: enumerations와 value_objects를 Neo4j에 저장하도록 개선

- `api/features/ingestion/event_storming/neo4j_ops/aggregates.py`
  - `create_aggregate`: enumerations와 value_objects 파라미터 추가 및 저장 로직 구현
  - `get_aggregates_by_bc`: enumerations와 valueObjects를 반환하도록 개선

### 참고한 backend-generators 파일
- `backend-generators/src/project_generator/workflows/aggregate_draft/aggregate_draft_generator.py`
  - `_get_response_schema` 메서드 (라인 60-171)
  - `_build_prompt` 메서드 (라인 378-479)
  - `_prepare_inputs` 메서드 (라인 190-213)
  - 전체 워크플로우 구조
