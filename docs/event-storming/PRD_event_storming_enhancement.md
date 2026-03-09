# Event Storming 생성 체인 개선 PRD

## 1. 개요

### 1.1 목적
기존 Event Storming 워크플로우를 유지하면서, 각 요소 추출 단계에서 backend-generators의 검증된 노하우(프롬프트, 생성 구조, 검증 로직)를 활용하여 더 정확하고 근거 있는 요소 추출을 구현합니다.

### 1.2 범위
- Event Storming 워크플로우의 각 노드 개선
- backend-generators의 workflows 노하우 통합
- 프롬프트 강화 및 검증 로직 추가
- Traceability 및 근거 추적 강화

### 1.3 비범위
- 기존 Event Storming 워크플로우 구조 변경 없음
- Human-in-the-loop 체크포인트 유지
- Neo4j 저장 로직 변경 없음

---

## 2. Event Storming 생성 체인 순서

### 2.1 전체 워크플로우
```
1. init → load_user_stories (User Stories 로드)
2. identify_bc (Bounded Context 추출)
3. approve_bc (Human-in-the-loop)
4. breakdown_user_story (User Story 분해)
5. extract_aggregates (Aggregate 추출)
6. approve_aggregates (Human-in-the-loop)
7. extract_commands (Command 추출)
8. extract_events (Event 추출)
9. identify_policies (Policy 추출)
10. approve_policies (Human-in-the-loop)
11. generate_gwt (Given/When/Then 생성 - 후처리)
12. save_to_graph (Neo4j 저장)
```

### 2.2 각 단계별 개선 포인트

| 단계 | 현재 노드 | 개선 대상 | backend-generators 참고 | 상태 |
|------|----------|----------|------------------------|------|
| 1 | `load_user_stories_node` | User Story 검증/정제 | `user_story_generator.py` | ✅ 완료 |
| 2 | `identify_bc_node` | BC 추출 프롬프트 강화 | `bounded_context_generator.py` | ✅ 완료 |
| 4 | `breakdown_user_story_node` | Breakdown 구조화 | 선택적 (Aggregate 추출에서 활용) | ⏸️ 선택적 |
| 5 | `extract_aggregates_node` | Aggregate 추출 강화 | `aggregate_draft_generator.py` | ✅ 완료 |
| 7 | `extract_commands_node` | Command 추출 강화 | `command_readmodel_extractor.py` | ✅ 완료 |
| 8 | `extract_events_node` | Event 추출 강화 | `requirements_validator.py` | ✅ 완료 |
| 9 | `identify_policies_node` | Policy 추출 강화 | - | ✅ 완료 |
| 11 | `generate_gwt_node` | GWT (Given/When/Then) 생성 | - | ✅ 완료 |

**중요 고려사항:**
- **Event 추출**: `requirements_validator`는 요구사항에서 프로세스 단계를 이벤트로 추출합니다. 현재 Event Storming은 Command → Event 순서이지만, 요구사항 기반 직접 추출도 고려해야 합니다.
- **Command/ReadModel 추출**: `command_readmodel_extractor`는 요구사항에서 Command/ReadModel을 추출하며, UI nodes로 사용될 수 있습니다. Aggregate 추출 전에 먼저 추출하는 것도 고려해야 합니다.

---

## 3. 단계별 개선 계획

### 3.1 Step 1: User Story 로드 및 검증 개선

**현재 상태:**
- `load_user_stories_node`: Neo4j에서 User Stories를 단순 로드
- 검증 로직 없음

**개선 방향:**
- backend-generators의 `user_story_generator.py` 노하우 활용:
  - RAG 기반 유사 패턴 검색
  - User Story 품질 검증
  - 중복 제거 및 정제

**구현 내용:**
1. **RAG 컨텍스트 검색 추가**
   - `RAGRetriever`를 활용한 유사 User Story 패턴 검색
   - 도메인 용어 검색 및 정규화
   - 유사 프로젝트 템플릿 참조

2. **User Story 검증 로직**
   - Role, Action, Benefit 완전성 체크
   - 중복 User Story 감지 및 병합
   - 우선순위 및 상태 검증

3. **파일 위치:**
   - `api/features/ingestion/event_storming/nodes_init.py` 또는 새 파일 생성
   - `api/features/ingestion/event_storming/nodes_user_stories.py` (새로 생성)

**참고 파일:**
- `backend-generators/src/project_generator/workflows/user_story/user_story_generator.py`
- `backend-generators/src/project_generator/workflows/common/rag_retriever.py`

---

### 3.2 Step 2: Bounded Context 추출 개선

**현재 상태:**
- `identify_bc_node`: 간단한 프롬프트로 BC 후보 추출
- 도메인 분류, PBC 매칭, traceability 없음
- 대용량 User Stories 처리 미흡

**개선 방향:**
- backend-generators의 `bounded_context_generator.py` 노하우 활용:
  - 상세한 Task Guidelines 프롬프트
  - 도메인 분류 전략 (Core/Supporting/Generic)
  - PBC(Pre-Built Component) 매칭
  - Traceability (refs) 추적
  - BC 관계 분석 및 설명
  - **대용량 User Stories 청킹 처리**

**구현 내용:**
1. **대용량 처리**
   - User Stories가 대용량일 경우 청킹 처리
   - 각 청크별 BC 추출
   - 결과 병합 및 중복 제거

2. **프롬프트 구조 강화**
   - `_build_task_guidelines()` 메서드 로직 통합
   - 도메인 분류 가이드라인 추가
   - PBC 매칭 규칙 적용
   - Relation Type 제약 조건 추가

3. **입력 데이터 구조화**
   - Actors와 Events를 XML 형식으로 변환
   - Line-numbered requirements 제공
   - Additional rules 및 aspect details 포함

4. **출력 검증 및 정제**
   - @ placeholder 제거
   - Traceability refs 검증
   - BC 관계 설명 생성

5. **파일 위치:**
   - `api/features/ingestion/event_storming/nodes_bounded_contexts.py` 수정
   - `api/features/ingestion/event_storming/prompts.py` 수정 (IDENTIFY_BC_FROM_STORIES_PROMPT 강화)

**참고 파일:**
- `backend-generators/src/project_generator/workflows/bounded_context/bounded_context_generator.py`
- 특히 `_build_task_guidelines()`, `_build_user_input()`, `_build_prompt()` 메서드

---

### 3.3 Step 4: User Story Breakdown 개선

**현재 상태:**
- `breakdown_user_story_node`: 기본적인 breakdown만 수행
- 도메인 개념 추출이 단순함

**분석:**
- User Story Breakdown은 이미 생성된 User Story를 **분해**하는 작업
- backend-generators의 `user_story_generator.py`는 User Story를 **생성**하는 작업
- 목적이 다르므로 직접적인 참고가 어려움

**개선 방향 (재검토 필요):**
- Breakdown은 Aggregate 추출을 위한 준비 단계
- Aggregate 추출 단계에서 더 상세한 분석이 이루어지므로, Breakdown은 간단하게 유지 가능
- 또는 Aggregate 추출 단계의 프롬프트에서 Breakdown 정보를 더 활용하도록 개선

**결론:**
- Step 4는 **선택적 개선**으로 분류
- 우선순위를 낮추고 Step 5 (Aggregate 추출)에 집중
- Aggregate 추출 단계에서 Breakdown 결과를 더 효과적으로 활용하도록 개선

---

### 3.4 Step 5: Aggregate 추출 개선

**현재 상태:**
- `extract_aggregates_node`: 기본적인 Aggregate 추출
- Invariants 및 구조 분석이 단순함
- 대용량 Breakdown 결과 처리 미흡

**개선 방향:**
- backend-generators의 `aggregate_draft_generator.py` 노하우 활용:
  - 여러 Aggregate 설계 옵션 생성
  - Pros/Cons 분석
  - Cohesion, Coupling, Consistency 분석
  - Enumerations 및 Value Objects 식별
  - **대용량 Breakdown 결과 청킹 처리**

**구현 내용:**
1. **대용량 처리**
   - Breakdown 결과가 대용량일 경우 청킹 처리
   - 각 청크별 Aggregate 추출
   - 결과 병합 및 중복 제거

2. **Aggregate 설계 옵션 생성**
   - 여러 구조 옵션 생성 (현재는 단일 옵션만)
   - 각 옵션의 Pros/Cons 분석
   - 설계 근거 제공

3. **구조 분석 강화**
   - Enumerations 식별 (items 포함)
   - Value Objects 식별 (fields 포함)
   - Aggregate 간 참조 관계 파악

4. **파일 위치:**
   - `api/features/ingestion/event_storming/nodes_aggregates.py` 수정
   - `api/features/ingestion/event_storming/prompts.py` 수정 (EXTRACT_AGGREGATES_PROMPT 강화)

**참고 파일:**
- `backend-generators/src/project_generator/workflows/aggregate_draft/aggregate_draft_generator.py`
- 특히 `_generate_draft()`, `_build_prompt()` 메서드

---

### 3.5 Step 7: Command 추출 개선

**현재 상태:**
- `extract_commands_node`: 기본적인 Command 추출
- Actor 및 Aggregate 매핑이 단순함

**개선 방향:**
- backend-generators의 `command_readmodel_extractor.py` 노하우 활용:
  - 청크 단위 처리 (대용량 요구사항)
  - 구조화된 Command 추출
  - Actor 분류 강화 (user, admin, system, external)
  - Aggregate 매핑 검증

**구현 내용:**
1. **청크 처리 로직**
   - 대용량 요구사항을 청크로 분할
   - 각 청크별 Command 추출
   - 결과 병합 및 중복 제거

2. **Command 구조화**
   - Actor 분류 강화
   - Aggregate 매핑 검증
   - Command 간 의존성 파악

3. **파일 위치:**
   - `api/features/ingestion/event_storming/nodes_commands.py` 수정
   - `api/features/ingestion/event_storming/prompts.py` 수정 (EXTRACT_COMMANDS_PROMPT 강화)

**참고 파일:**
- `backend-generators/src/project_generator/workflows/sitemap/command_readmodel_extractor.py`
- 특히 `extract_commands_and_readmodels()`, `split_requirements_into_chunks()` 메서드

---

### 3.6 Step 8: Event 추출 개선

**현재 상태:**
- `extract_events_node`: 기본적인 Event 추출
- Command-Event 매핑이 단순함
- Event 명명 규칙 및 검증이 부족함
- 대용량 요구사항 처리 미흡

**개선 방향:**
- backend-generators의 `requirements_validator.py` 노하우 활용:
   - Event Discovery Methodology 적용
   - 상세한 Event 추출 프롬프트 구조
   - Source Traceability (refs) 처리
   - Line-numbered requirements 활용
   - Event refs 변환 로직
   - **대용량 요구사항 청킹 처리**

**구현 내용:**
1. **대용량 처리**
   - 요구사항이 대용량일 경우 청킹 처리
   - 각 청크별 Event 추출
   - 결과 병합 및 중복 제거

2. **Event Discovery Methodology 적용**
   - Comprehensive Coverage: 모든 중요한 비즈니스 순간을 도메인 이벤트로 변환
   - Complete State Capture: 모든 비즈니스적으로 중요한 상태 변경을 이벤트로 표현
   - Flow Completeness: Happy path와 예외 흐름 모두 포함
   - State Change Focus: 비즈니스적으로 중요한 상태 변경만 이벤트화 (읽기 전용 작업 제외)
   - Primary Business Actions: 주요 비즈니스 액션에 집중

3. **Event 명명 규칙 강화**
   - PascalCase 및 Past Participle 형식 강제 (예: OrderPlaced, PaymentProcessed)
   - 명명 규칙 검증 로직 추가

4. **Source Traceability (refs) 처리**
   - Line-numbered requirements 제공
   - Event refs 변환 로직 (`_convert_event_refs`, `_sanitize_and_convert_refs`)
   - Requirements line number와의 연결 강화

5. **Command-Event 매핑 검증**
   - 모든 Command가 Event를 emit하는지 확인
   - Event가 적절한 Command에서 발생하는지 검증
   - Event 체인 완전성 검증

6. **파일 위치:**
   - `api/features/ingestion/event_storming/nodes_events.py` 수정
   - `api/features/ingestion/event_storming/prompts.py` 수정 (EXTRACT_EVENTS_PROMPT 강화)

**참고 파일:**
- `backend-generators/src/project_generator/workflows/requirements_validation/requirements_validator.py`
- 특히 `_build_prompt()` 메서드의 Event Discovery Methodology
- `_convert_event_refs()`, `_sanitize_and_convert_refs()` 메서드
- `_add_line_numbers()` 메서드

---

### 3.7 Step 11: Given/When/Then (GWT) 생성

**현재 상태:**
- `generate_gwt_node`: Command와 Policy에 대한 GWT 구조 생성
- 모든 요소(Command, Event, Aggregate, Policy)가 생성된 후 후처리 단계로 실행
- Neo4j에 별도 노드로 저장되며, UI에서는 Command/Policy에 종속된 필드로 표시

**개선 방향:**
- Command, Event, Aggregate, Policy의 모든 정보가 준비된 상태에서 GWT 생성
- 참조된 노드의 properties를 `fieldValues`로 자동 매핑
- BDD 스타일 테스트 시나리오 생성 지원

**구현 내용:**
1. **후처리 단계 실행**
   - `approve_policies` 이후, `save_to_graph` 이전에 실행
   - 모든 Command, Event, Aggregate, Policy 정보가 state에 준비된 상태

2. **GWT 구조 생성**
   - **Given**: Command 자체 또는 Policy의 trigger Event
   - **When**: Aggregate (Command를 처리하는 Aggregate)
   - **Then**: Event (Command가 emit하는 Event)

3. **fieldValues 자동 매핑**
   - Command의 properties → `given.fieldValues`
   - Aggregate의 properties → `when.fieldValues`
   - Event의 properties → `then.fieldValues`
   - LLM이 참조된 노드의 properties를 분석하여 적절한 테스트 값을 생성

4. **Neo4j 저장**
   - `Given`, `When`, `Then` 노드를 별도로 생성
   - `HAS_GIVEN`, `HAS_WHEN`, `HAS_THEN` 관계로 Command/Policy와 연결
   - `REFERENCES` 관계로 참조된 노드(Aggregate, Command, Event)와 연결
   - `fieldValues`는 JSON 문자열로 저장

5. **UI 통합**
   - GWT는 Neo4j에서는 별도 노드이지만, UI에서는 Command/Policy 노드 내부에 필드로 표시
   - Inspector Panel에서 GWT 편집 가능
   - `fieldValues` 키-값 쌍을 추가/수정/삭제 가능

6. **파일 위치:**
   - `api/features/ingestion/event_storming/nodes_gwt.py` (생성됨)
   - `api/features/ingestion/event_storming/neo4j_ops/gwt.py` (생성됨)
   - `api/features/ingestion/event_storming/prompts.py` (GENERATE_GWT_PROMPT 추가)
   - `docs/cypher/schema/03_node_types.cypher` (Given/When/Then 노드 타입 추가)
   - `docs/cypher/schema/04_relationships.cypher` (GWT 관계 추가)

**워크플로우 위치:**
- `approve_policies` → `generate_gwt` → `save_to_graph`
- 모든 참조 정보가 준비된 후 실행되므로 정확한 매핑 가능

**특징:**
- **후처리 방식**: 초기 생성 단계에서는 GWT를 생성하지 않고, 모든 요소가 완성된 후 생성
- **동적 필드 추가**: Pydantic 모델에서 GWT 필드를 제외하여 structured output 스키마 유지
- **런타임 추가**: `setattr()`를 사용하여 런타임에 GWT 필드를 동적으로 추가
- **안전한 접근**: `getattr()`를 사용하여 동적으로 추가된 필드에 안전하게 접근

---

## 4. 공통 개선 사항

### 4.1 대용량 요청 처리 (스캐닝 및 청킹)

**요구사항:**
- **모든 추출 단계**에서 대용량 요청이 들어와도 안정적으로 처리되어야 함
- 요구사항 문서, User Stories, Breakdown 결과 등이 대용량일 경우를 대비

**구현 방향:**
1. **스캐닝 단계**
   - 입력 데이터 크기 측정
   - LLM 토큰 제한 확인
   - 청킹 필요 여부 판단

2. **청킹 처리**
   - 대용량 입력을 의미 있는 단위로 분할
   - 각 청크별로 추출 수행
   - 결과 병합 및 중복 제거
   - 일관성 검증

3. **적용 대상:**
   - **User Story 추출** (Step 1): 대용량 요구사항 처리 - ✅ 완료
   - **BC 추출** (Step 2): 대용량 User Stories 처리 - ✅ 완료
   - **Aggregate 추출** (Step 5): BC 단위로 개별 처리되므로 청킹 미필요 - ⏸️ 구현 미필요
   - **Command 추출** (Step 7): Aggregate 단위로 개별 처리되므로 청킹 미필요 - ⏸️ 구현 미필요
   - **Event 추출** (Step 8): Aggregate 단위로 개별 처리되므로 청킹 미필요 - ⏸️ 구현 미필요
   - **Policy 추출** (Step 9): 대용량 Event/Command 처리 - ✅ 완료
   - **GWT 생성** (Step 11): Command/Policy 단위로 개별 처리되므로 청킹 미필요 - ⏸️ 구현 미필요

4. **참고 구현:**
   - `backend-generators/src/project_generator/workflows/sitemap/command_readmodel_extractor.py`
   - `split_requirements_into_chunks()` 메서드 패턴 활용

### 4.2 Traceability 강화
- 모든 요소에 `user_story_ids` 추적
- Requirements line number 참조 (refs)
- `RefsTraceUtil` 활용

### 4.3 검증 로직 추가
- 각 단계별 출력 검증
- 일관성 체크
- 중복 제거

### 4.4 에러 처리
- 각 단계별 에러 핸들링 강화
- 부분 실패 시 복구 로직
- 사용자 피드백 반영

---

## 5. 구현 우선순위

### Phase 1: 핵심 개선 (우선순위 높음) - ✅ 완료
1. **User Story 로드 및 검증 개선** (Step 1) - ✅ 완료
   - 필수 필드 검증, 중복 제거, 우선순위/상태 검증

2. **Bounded Context 추출 개선** (Step 2) - ✅ 완료
   - 도메인 분류 전략, Core Principles, Task Guidelines 강화

### Phase 2: 핵심 개선 (우선순위 높음) - ✅ 완료

**완료된 개선 사항:**

1. **Aggregate 추출 개선** (Step 5) - ✅ 완료
   - 설계 옵션 및 Pros/Cons 분석
   - Enumerations 및 Value Objects 식별
   - Aggregate 구조 분석 강화

2. **Command 추출 개선** (Step 7) - ✅ 완료
   - 구조화된 Command 추출
   - Actor 분류 강화
   - Aggregate와의 매핑 검증

3. **Event 추출 개선** (Step 8) - ✅ 완료
   - Event Discovery Methodology 적용
   - Command-Event 매핑 검증
   - Event 명명 규칙 강화

4. **Policy 추출 개선** (Step 9) - ✅ 완료
   - Cross-BC Policy 식별
   - Event-Command 매핑 검증

5. **GWT 생성 추가** (Step 11) - ✅ 완료
   - Given/When/Then 구조 생성
   - fieldValues 자동 매핑
   - 후처리 방식으로 모든 참조 정보 활용
   - Neo4j 별도 노드 저장 및 UI 통합

**결정 사항:**
- 현재 순서 유지 (Aggregate → Command → Event → Policy → GWT)
- 모든 요소 생성 후 GWT를 후처리로 생성하여 정확한 참조 매핑 가능

### Phase 3: 대용량 요청 처리 - 🔄 부분 완료

**목표:**
- 모든 추출 단계에서 대용량 요청을 안정적으로 처리
- 청킹 및 병합 로직 구현

**완료된 구현:**
1. **User Story 추출** (Step 1): 대용량 요구사항 처리 - ✅ 완료
   - `split_text_with_overlap()` 활용한 텍스트 청킹
   - `merge_chunk_results()` 활용한 결과 병합 및 중복 제거
   - `calculate_chunk_progress()` 활용한 진행률 계산

2. **BC 추출** (Step 2): 대용량 User Stories 처리 - ✅ 완료
   - `split_list_with_overlap()` 활용한 리스트 청킹
   - `merge_chunk_results()` 활용한 결과 병합 및 중복 제거
   - `dedupe_key` 기반 중복 제거 (key, name, id 우선순위)

3. **Policy 추출** (Step 9): 대용량 Event/Command 처리 - ✅ 완료
   - `split_text_with_overlap()` 활용한 텍스트 청킹
   - `merge_chunk_results()` 활용한 결과 병합 및 중복 제거

**구현 미필요 (이미 개별 단위로 처리됨):**
4. **Aggregate 추출** (Step 5): BC 단위로 개별 LLM 호출하므로 청킹 불필요
5. **Command 추출** (Step 7): Aggregate 단위로 개별 LLM 호출하므로 청킹 불필요
6. **Event 추출** (Step 8): Aggregate 단위로 개별 LLM 호출하므로 청킹 불필요
7. **GWT 생성** (Step 11): Command/Policy 단위로 개별 LLM 호출하므로 청킹 불필요

**참고:**
- Aggregate, Command, Event, GWT는 이미 BC → Aggregate → Command/Event 단위로 분할되어 개별 처리되므로, 추가 청킹이 필요하지 않습니다.
- 각 단계에서 입력 데이터가 이미 작은 단위로 제한되어 있어 토큰 제한을 초과할 가능성이 낮습니다.

**구현된 유틸리티:**
- `api/features/ingestion/workflow/utils/chunking.py`: 공통 청킹 유틸리티
  - `estimate_tokens()`: 토큰 수 추정
  - `should_chunk()`: 청킹 필요 여부 판단
  - `split_text_with_overlap()`: 텍스트 청킹 (overlap 지원)
  - `split_list_with_overlap()`: 리스트 청킹 (overlap 지원)
  - `merge_chunk_results()`: 결과 병합 및 중복 제거
  - `calculate_chunk_progress()`: 청크별 진행률 계산

**참고 구현:**
- `backend-generators/src/project_generator/workflows/sitemap/command_readmodel_extractor.py`
- `split_requirements_into_chunks()` 메서드 패턴 활용

### Phase 4: 보완 개선 (우선순위 중간)
4. **User Story Breakdown 개선** (Step 4) - 선택적
   - Breakdown은 Aggregate 추출의 준비 단계
   - Aggregate 추출 단계에서 Breakdown 결과를 더 효과적으로 활용하도록 개선하는 것이 더 유용할 수 있음

---

## 6. 기술 스택

### 6.1 기존 기술
- LangGraph (워크플로우 관리)
- LangChain (LLM 통합)
- Pydantic (Structured Output)
- Neo4j (데이터 저장)

### 6.2 추가 필요 기술
- RAG Retriever (backend-generators에서 참고)
- XML Util (backend-generators에서 참고)
- RefsTraceUtil (backend-generators에서 참고)

---

## 7. 성공 지표

### 7.1 품질 지표
- BC 추출 정확도 향상 (도메인 분류 정확도)
- Aggregate 설계 품질 향상 (Pros/Cons 분석 완성도)
- Command/Event 매핑 정확도 향상

### 7.2 추적성 지표
- 모든 요소의 `user_story_ids` 연결률 100%
- Requirements refs 연결률 90% 이상

### 7.3 사용자 만족도
- Human-in-the-loop 승인률 향상
- 피드백 반영 속도 개선

---

## 8. 리스크 및 대응

### 8.1 리스크
1. **프롬프트 복잡도 증가로 인한 LLM 비용 증가**
   - 대응: 프롬프트 최적화 및 캐싱

2. **기존 워크플로우와의 호환성 문제**
   - 대응: 점진적 통합 및 테스트

3. **backend-generators 의존성 관리**
   - 대응: 필요한 로직만 추출하여 독립적으로 구현

### 8.2 완화 전략
- 단계별 구현 및 테스트
- 기존 기능 유지 보장
- 롤백 계획 수립

---

## 9. 다음 단계

### 9.1 현재 상태
- ✅ **Phase 1 완료**: User Story 검증, BC 추출 개선
- ✅ **Phase 2 완료**: Aggregate, Command, Event, Policy 추출 개선, GWT 생성 추가
- ✅ **Phase 3 완료**: 대용량 요청 처리 (User Story, BC, Policy 청킹 완료, 나머지는 개별 처리로 청킹 불필요)

### 9.2 Phase 3 구현 계획
1. **대용량 처리 로직 구현**
   - 각 추출 단계에 청킹 로직 추가
   - 결과 병합 및 중복 제거 로직 구현
   - 일관성 검증 로직 추가

2. **테스트 계획**
   - 대용량 입력 데이터로 각 단계 테스트
   - 청킹 및 병합 로직 검증
   - 성능 및 정확도 측정

3. **문서화**
   - 청킹 전략 문서화
   - 병합 로직 설명
   - 성능 가이드라인 작성

---

## 10. TODO: 향후 개선 사항

### 10.1 Human-in-the-loop 피드백 반영 개선

**현재 문제점:**
- `approve_*_node`에서 피드백을 받아도, 재생성 노드(`extract_*_node`, `identify_*_node`)에서 피드백이 프롬프트에 반영되지 않음
- `messages` 히스토리에 피드백이 저장되지만, LLM 호출 시 사용되지 않음
- 결과적으로 피드백이 반영되지 않은 동일한 결과가 재생성됨

**개선 방안:**
1. **피드백을 프롬프트에 포함**
   - `extract_aggregates_node`, `identify_bc_node`, `identify_policies_node` 등에서
   - `state.messages`에서 최근 HumanMessage 피드백을 추출
   - 프롬프트에 `<human_feedback>` 섹션 추가하여 피드백 반영

2. **이전 생성 결과와 피드백을 함께 제공**
   - 피드백이 있을 경우, 이전에 생성된 후보들(`state.aggregate_candidates`, `state.bc_candidates` 등)을 프롬프트에 포함
   - "다음은 이전에 생성된 결과입니다. 피드백을 반영하여 수정해주세요" 형태로 제공

3. **구현 예시:**
   ```python
   # extract_aggregates_node에서
   feedback_context = ""
   previous_candidates = ""
   
   if state.messages:
       # 최근 피드백 찾기
       for msg in reversed(state.messages):
           if isinstance(msg, HumanMessage) and msg.content.upper() != "APPROVED":
               feedback_context = f"\n\n<human_feedback>\n{msg.content}\n</human_feedback>\n"
               break
       
       # 이전 생성 결과 포함
       if state.aggregate_candidates:
           previous_candidates = format_previous_aggregates(state.aggregate_candidates)
   
   prompt = EXTRACT_AGGREGATES_PROMPT.format(...) + feedback_context
   if previous_candidates:
       prompt += f"\n\n<previous_result>\n{previous_candidates}\n</previous_result>\n"
   ```

**영향받는 노드:**
- `extract_aggregates_node` (피드백: `approve_aggregates_node`)
- `identify_bc_node` (피드백: `approve_bc_node`)
- `identify_policies_node` (피드백: `approve_policies_node`)

**우선순위:** 중간 (현재는 피드백이 무시되지만, 기본 기능은 동작함)

**참고:**
- backend-generators의 `_feedback_prompt` 메서드 패턴 참고 가능
- LangGraph의 `messages` 히스토리 활용

---

### 10.2 Human-in-the-loop 일시정지 및 채팅 연동

**현재 상태:**
- ✅ **일시정지/재개 기능 구현 완료**
  - 각 phase에서 `wait_if_paused()` 체크포인트 구현
  - UI에서 일시정지/재개 버튼 제공
  - 일시정지 메시지: "⏸️ 일시 정지됨 (채팅으로 일부를 수정한 후 재개하세요)"
  - `IngestionSession.is_paused` 플래그로 상태 관리

- ❌ **채팅 연동 미완성**
  - 일시정지 후 채팅으로 생성된 데이터를 수정하는 기능이 없음
  - 채팅에서 수정한 내용이 재개 시 workflow context에 반영되지 않음
  - IngestionSession과 채팅 세션 간 연결이 없음

**개선 방안:**
1. **일시정지 시점의 컨텍스트 저장**
   - 현재 생성된 데이터(User Stories, BCs, Aggregates 등)를 채팅에서 접근 가능하게
   - `IngestionSession`에 현재 생성 상태 스냅샷 저장
   - 채팅 세션과 IngestionSession 연결

2. **채팅에서 수정 기능**
   - 사용자가 채팅으로 생성된 요소를 수정/삭제/추가
   - Neo4j에서 직접 수정하거나, 채팅을 통해 LLM이 수정 제안
   - 수정사항을 `IngestionWorkflowContext`에 반영

3. **재개 시 수정사항 반영**
   - `wait_if_paused()`에서 재개 시 수정사항 확인
   - `IngestionWorkflowContext`에 수정사항 반영
   - 다음 phase가 수정된 데이터를 사용하도록

4. **구현 예시:**
   ```python
   # 일시정지 시 컨텍스트 저장
   if session.is_paused:
       session.snapshot = {
           "user_stories": ctx.user_stories,
           "bounded_contexts": ctx.bounded_contexts,
           "aggregates": ctx.aggregates_by_bc,
           # ... 기타 생성된 데이터
       }
       # 채팅 세션과 연결
       link_chat_session_to_ingestion(session.id, chat_session_id)
   
   # 재개 시 수정사항 확인
   if session.snapshot:
       modified_data = get_chat_modifications(chat_session_id)
       if modified_data:
           # context에 수정사항 반영
           apply_modifications_to_context(ctx, modified_data)
   ```

**영향받는 컴포넌트:**
- `api/features/ingestion/ingestion_sessions.py`: 스냅샷 저장 로직
- `api/features/ingestion/ingestion_workflow_runner.py`: 재개 시 수정사항 반영
- `api/features/ingestion/workflow/ingestion_workflow_context.py`: 수정사항 적용
- 채팅 기능: IngestionSession과의 연동

**우선순위:** 높음 (Human-in-the-loop의 핵심 기능)

**참고:**
- 현재 일시정지 기능은 구현되어 있으나, 실제 human-in-the-loop를 위해서는 채팅 연동이 필수
- Event Storming 워크플로우의 `approve_*_node`와 유사한 패턴 활용 가능

---

### 10.3 생성 중단 기능 및 오류 처리 개선

**완료된 구현:**
- ✅ **중단 기능 구현 완료**
  - `/api/ingest/{session_id}/cancel` 엔드포인트 추가
  - `IngestionSession.is_cancelled` 플래그 추가
  - 각 phase에서 `is_cancelled` 체크 및 즉시 중단
  - `workflow_task.cancel()` 호출로 비동기 작업 취소
  - UI에 중단 버튼 추가

- ✅ **오류 알림 개선**
  - 오류 발생 시 상세 메시지 표시 (`data.data?.error` 포함)
  - Floating panel에 오류 메시지 영역 추가
  - EventSource 연결 오류 시 명확한 메시지 표시
  - 오류 발생 시 자동으로 연결 종료 및 상태 초기화

**구현 위치:**
- `api/features/ingestion/router.py`: cancel 엔드포인트
- `api/features/ingestion/ingestion_workflow_runner.py`: 중단 체크 로직
- `api/features/ingestion/ingestion_sessions.py`: is_cancelled 플래그
- `frontend/src/features/requirementsIngestion/ui/RequirementsIngestionModal.vue`: UI 개선

---

### 10.4 User Story 품질 개선

**완료된 구현:**
- ✅ **Role 검증 강화**
  - 프롬프트에 구체적인 role 요구사항 명시 ("user", "사용자", 빈 문자열 금지)
  - 저장 전 최종 검증: 빈 role 또는 generic role인 경우 추론 시도
  - `_infer_role_from_context()` 함수로 action/benefit에서 role 추론
  - 추론 실패 시 "customer"로 fallback

- ✅ **중복 제거 개선**
  - 프론트엔드에서 `createdItems` 중복 체크 및 업데이트
  - Neo4j에서 `MERGE` 연산으로 id 기반 중복 방지
  - 청크 병합 시 `dedupe_key` 기반 중복 제거

**구현 위치:**
- `api/features/ingestion/requirements_to_user_stories.py`: role 추론 로직
- `api/features/ingestion/workflow/phases/user_stories.py`: 최종 검증 로직
- `frontend/src/features/requirementsIngestion/ui/RequirementsIngestionModal.vue`: 중복 제거
