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
11. save_to_graph (Neo4j 저장)
```

### 2.2 각 단계별 개선 포인트

| 단계 | 현재 노드 | 개선 대상 | backend-generators 참고 | 우선순위 |
|------|----------|----------|------------------------|---------|
| 1 | `load_user_stories_node` | User Story 검증/정제 | `user_story_generator.py` | ✅ 완료 |
| 2 | `identify_bc_node` | BC 추출 프롬프트 강화 | `bounded_context_generator.py` | ✅ 완료 |
| 4 | `breakdown_user_story_node` | Breakdown 구조화 | 선택적 (Aggregate 추출에서 활용) | 낮음 |
| 5 | `extract_aggregates_node` | Aggregate 추출 강화 | `aggregate_draft_generator.py` | 높음 |
| 7 | `extract_commands_node` | Command 추출 강화 | `command_readmodel_extractor.py` | 높음 |
| 8 | `extract_events_node` | Event 추출 강화 | `requirements_validator.py` | 높음 |

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
   - **BC 추출** (Step 2): 대용량 User Stories 처리
   - **Aggregate 추출** (Step 5): 대용량 Breakdown 결과 처리
   - **Command 추출** (Step 7): 대용량 요구사항 처리 (이미 명시됨)
   - **Event 추출** (Step 8): 대용량 요구사항 처리
   - **Policy 추출** (Step 9): 대용량 Event/Command 처리

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

### Phase 2: 핵심 개선 (우선순위 높음) - 진행 중

**⚠️ 중요 고려사항:**

#### A. Event 추출 방식 재검토 필요
- **현재 Event Storming**: Command → Event 순서 (Command가 emit하는 Event 추출)
- **`requirement_validator`**: 요구사항에서 프로세스의 각 단계를 이벤트로 직접 추출
- **고려사항**: 두 방식을 결합하거나, 요구사항 기반 Event 추출을 먼저 수행한 후 Command와 매핑하는 방식 고려

#### B. Command/ReadModel 추출 순서 재검토 필요
- **현재 Event Storming**: Aggregate → Command 순서
- **`command_readmodel_extractor`**: 요구사항에서 Command/ReadModel을 직접 추출 (Aggregate 정보 필요)
- **고려사항**: 
  - Command/ReadModel은 UI nodes로 사용될 수 있음
  - Aggregate 추출 전에 먼저 추출하는 것도 고려 가능
  - 또는 Aggregate 추출 후 Command/ReadModel을 더 정확하게 매핑

#### C. 추천 우선순위

**Option 1: 현재 순서 유지 (추천)**
1. **Aggregate 추출 개선** (Step 5) - 다음 단계
   - 설계 옵션 및 Pros/Cons 분석
   - Enumerations 및 Value Objects 식별
   - Aggregate 구조가 명확해지면 Command/ReadModel 매핑이 더 정확해짐

2. **Command 추출 개선** (Step 7)
   - `command_readmodel_extractor.py` 노하우 활용
   - 청크 처리, 구조화된 Command 추출
   - Actor 분류 강화
   - Aggregate와의 매핑 검증

3. **Event 추출 개선** (Step 8)
   - `requirements_validator.py` 노하우 활용
   - Event Discovery Methodology 적용
   - Command-Event 매핑 검증

**Option 2: 순서 변경 (대안)**
- BC 추출 후 → Command/ReadModel 추출 → Aggregate 추출 → Event 추출
- 장점: Command/ReadModel을 UI nodes로 먼저 활용 가능
- 단점: Aggregate 정보 없이 Command 추출 시 매핑이 부정확할 수 있음

### Phase 3: 보완 개선 (우선순위 중간)
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

1. **Phase 1 구현 시작**
   - Bounded Context 추출 개선부터 시작
   - 프롬프트 구조 분석 및 통합

2. **테스트 계획 수립**
   - 각 단계별 단위 테스트
   - 통합 테스트 시나리오 작성

3. **문서화**
   - 개선된 프롬프트 문서화
   - 사용 가이드 작성

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
