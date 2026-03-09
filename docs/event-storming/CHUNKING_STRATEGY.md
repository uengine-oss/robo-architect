# 대용량 요구사항 처리 전략 (Chunking & Parallel Processing)

## 1. 개요

### 1.1 목적
Event Storming 생성 프로세스에서 대용량 요구사항 문서를 안정적으로 처리하기 위한 청킹 및 병렬 처리 전략입니다.

### 1.2 핵심 원칙
1. **단계별 독립 청킹**: 각 phase는 독립적으로 청킹 처리
2. **맥락 유지**: Overlapping을 통한 분할 지점의 앞뒤 문장 보존
3. **결과 병합**: 각 청크별 결과를 병합하고 중복 제거
4. **병렬 처리**: 모든 요소 생성 작업은 `asyncio.gather`를 사용하여 병렬 처리
5. **타임아웃 보장**: LLM 호출 및 Neo4j 작업에 명시적 타임아웃 적용

---

## 2. 청킹 전략

### 2.1 Phase별 청킹 적용 현황

| Phase | 청킹 적용 | 청킹 기준 | 병렬 처리 | 상태 |
|-------|----------|----------|----------|------|
| `extract_user_stories_phase` | ✅ | 텍스트 토큰 > 100k | ✅ | ✅ 완료 |
| `identify_bounded_contexts_phase` | ✅ | 리스트 개수 > 50 또는 토큰 > 100k | ✅ | ✅ 완료 |
| `identify_policies_phase` | ✅ | 프롬프트 토큰 > 100k | ✅ | ✅ 완료 |
| `extract_aggregates_phase` | ❌ | 불필요 (BC별 처리, 입력 작음) | ✅ | ✅ 완료 |
| `extract_commands_phase` | ✅ | 프롬프트 토큰 > 100k (Aggregate별) | ✅ | ✅ 완료 |
| `extract_events_phase` | ❌ | 불필요 (Aggregate별 처리, 입력 작음) | ✅ | ✅ 완료 |
| `extract_readmodels_phase` | ✅ | 프롬프트 토큰 > 100k (BC별) | ✅ | ✅ 완료 |
| `generate_gwt_phase` | ✅ | 리스트 개수 > 8 또는 토큰 > 60k | ✅ | ✅ 완료 |
| `generate_ui_wireframes_phase` | ❌ | 불필요 (ReadModel별 개별 처리) | ✅ | ✅ 완료 |

### 2.2 청킹 기준

#### 텍스트 기반 청킹
- **함수**: `should_chunk(text, max_tokens=100000)`
- **기준**: 텍스트의 토큰 수가 100k를 초과하면 청킹 필요
- **적용 대상**:
  - `extract_user_stories_phase`: 원본 요구사항 문서
  - `identify_policies_phase`: Events/Commands 프롬프트
  - `extract_commands_phase`: User Stories 프롬프트 (Aggregate별)
  - `extract_readmodels_phase`: User Stories/Events 프롬프트 (BC별)

#### 리스트 기반 청킹
- **함수**: `should_chunk_list(items, item_to_text, max_items, max_tokens)`
- **기준**:
  1. 아이템 개수가 `max_items`를 초과하면 청킹 필요
  2. 또는 아이템을 텍스트로 변환했을 때 토큰 수가 `max_tokens`를 초과하면 청킹 필요
- **적용 대상**:
  - `identify_bounded_contexts_phase`: User Stories 리스트 (max_items=50)
  - `generate_gwt_phase`: Commands 리스트 (max_items=8, max_tokens=60000)

### 2.3 청킹 파라미터

```python
DEFAULT_MAX_TOKENS = 100000  # 입력용 토큰 제한 (출력 여유 포함)
DEFAULT_CHUNK_SIZE = 80000   # 실제 청크 크기 (안전 마진 포함)
DEFAULT_OVERLAP_SIZE = 2000  # Overlapping 크기 (문자 단위)
```

**Phase별 청크 크기:**
- `extract_user_stories_phase`: DEFAULT_CHUNK_SIZE (80k)
- `identify_bounded_contexts_phase`: 30개 User Stories (overlap: 3개)
- `identify_policies_phase`: DEFAULT_CHUNK_SIZE (80k)
- `generate_gwt_phase`: 8개 Commands (overlap: 1개, max_tokens: 60k)

---

## 3. 병렬 처리 전략

### 3.1 병렬 처리 적용 현황

**모든 phase에서 요소 생성 작업은 병렬 처리됩니다:**

1. **User Stories**: `asyncio.gather`로 모든 User Story 생성 병렬 처리
2. **Bounded Contexts**: `asyncio.gather`로 모든 BC 생성 및 User Story 연결 병렬 처리
3. **Aggregates**: `asyncio.gather`로 Aggregate별 생성 병렬 처리
4. **Commands**: `asyncio.gather`로 Command별 생성 및 User Story 연결 병렬 처리
5. **Events**: `asyncio.gather`로 Event별 생성 및 User Story 연결 병렬 처리
6. **ReadModels**: `asyncio.gather`로 ReadModel별 생성 및 User Story 연결 병렬 처리
7. **Policies**: `asyncio.gather`로 Policy별 생성 및 User Story 연결 병렬 처리
8. **GWT**: 청크 내 모든 Command의 GWT 생성 병렬 처리
9. **UI Wireframes**: `asyncio.gather`로 UI별 생성 병렬 처리

### 3.2 병렬 처리 패턴

**공통 패턴:**
```python
# 1. Helper 함수 생성 (async)
async def _create_X_with_links(x, idx, total, ctx):
    # 개별 요소 생성 및 연결 로직
    pass

# 2. 모든 요소에 대한 Task 수집
tasks = []
for idx, x in enumerate(items):
    tasks.append(_create_X_with_links(x, idx, len(items), ctx))

# 3. 병렬 실행
results = await asyncio.gather(*tasks, return_exceptions=True)

# 4. 결과 처리
for result in results:
    if isinstance(result, Exception):
        # 에러 처리
    else:
        # 성공 처리
```

### 3.3 타임아웃 보장

**모든 외부 호출에 타임아웃 적용:**
- **LLM 호출**: `asyncio.wait_for(..., timeout=300)` (5분)
- **Neo4j 생성**: `asyncio.wait_for(..., timeout=10)` (10초)
- **Neo4j 연결**: `asyncio.wait_for(..., timeout=5)` (5초)

---

## 4. Phase별 상세 구현

### 4.1 `extract_user_stories_phase`

**청킹:**
- 원본 요구사항 문서(`ctx.content`) 직접 사용
- 토큰 수 > 100k 시 `split_text_with_overlap()` 사용
- 문단 단위 분할, overlap: 2-3개 문단

**병렬 처리:**
- 각 User Story 생성은 `_create_user_story_with_verification()` helper 함수 사용
- `asyncio.gather`로 모든 User Story 생성 병렬 처리

**결과 병합:**
- `merge_chunk_results()` 사용
- 중복 제거: `role:action:benefit` 조합
- ID 재할당: 청크별 임시 ID → 최종 순차 ID

### 4.2 `identify_bounded_contexts_phase`

**청킹:**
- User Stories 리스트 사용
- 개수 > 50개 또는 토큰 수 > 100k 시 `split_list_with_overlap()` 사용
- 청크 크기: 30개 (overlap: 3개)

**병렬 처리:**
- 각 BC 생성은 `_create_bc_with_links()` helper 함수 사용
- `asyncio.gather`로 모든 BC 생성 및 User Story 연결 병렬 처리

**결과 병합:**
- `merge_chunk_results()` 사용
- 중복 제거: `key`, `name`, 또는 `id` 기준

### 4.3 `identify_policies_phase`

**청킹:**
- Events/Commands 프롬프트 사용
- 전체 프롬프트 토큰 수 > 100k 시 `split_text_with_overlap()` 사용
- Events 텍스트 중심으로 청킹

**병렬 처리:**
- 각 Policy 생성은 `_create_policy_with_links()` helper 함수 사용
- `asyncio.gather`로 모든 Policy 생성 및 User Story 연결 병렬 처리
- User Story 연결은 배치 처리 (BATCH_SIZE=5)

**결과 병합:**
- `merge_chunk_results()` 사용
- 중복 제거: `name` 또는 `id` 기준

### 4.4 `extract_commands_phase`

**청킹:**
- Aggregate별 User Stories 프롬프트 사용
- 프롬프트 토큰 수 > 100k 시 `split_text_with_overlap()` 사용

**병렬 처리:**
- 각 Command 생성은 `_create_command_with_links()` helper 함수 사용
- Aggregate별로 모든 Command 생성 병렬 처리

**결과 병합:**
- Aggregate별로 결과 병합
- 중복 제거: `name` 또는 `id` 기준

### 4.5 `extract_events_phase`

**청킹:**
- 불필요 (Aggregate별 처리, Commands는 보통 적음)

**병렬 처리:**
- 각 Event 생성은 `_create_event_with_links()` helper 함수 사용
- Aggregate별로 모든 Event 생성 병렬 처리

### 4.6 `extract_readmodels_phase`

**청킹:**
- BC별 User Stories/Events 프롬프트 사용
- 프롬프트 토큰 수 > 100k 시 `split_text_with_overlap()` 사용
- User Stories와 Events를 각각 청킹하여 더 많은 청크 수 기준으로 처리

**병렬 처리:**
- 각 ReadModel 생성은 `_create_readmodel_with_links()` helper 함수 사용
- BC별로 모든 ReadModel 생성 병렬 처리

### 4.7 `generate_gwt_phase`

**청킹:**
- Commands 리스트 사용
- 개수 > 8개 또는 토큰 수 > 60k 시 `split_list_with_overlap()` 사용
- 청크 크기: 8개 Commands (overlap: 1개)
- 보수적 청크 크기로 토큰 오버플로우 방지

**병렬 처리:**
- 각 Command의 GWT 생성은 `_generate_gwt_for_command()` helper 함수 사용
- 청크 내 모든 Command의 GWT 생성 병렬 처리
- 청크 간에는 순차 처리 (토큰 제한 고려)

**특징:**
- Policy GWT 생성은 비활성화됨
- Command GWT의 "when" 필드에 Policy 정보 포함

### 4.8 `generate_ui_wireframes_phase`

**청킹:**
- 불필요 (ReadModel별 개별 처리)

**병렬 처리:**
- 각 UI 생성은 `_llm_invoke_to_html()` helper 함수 사용
- 배치 처리 (BATCH_SIZE=10)로 UI 생성 병렬 처리

---

## 5. 공통 유틸리티

### 5.1 청킹 유틸리티 (`api/features/ingestion/workflow/utils/chunking.py`)

**주요 함수:**
- `estimate_tokens(text, model)`: 텍스트 토큰 수 추정
- `should_chunk(text, max_tokens)`: 텍스트 기반 청킹 필요 여부
- `should_chunk_list(items, item_to_text, max_items, max_tokens)`: 리스트 기반 청킹 필요 여부
- `split_text_with_overlap(text, chunk_size, overlap_size)`: 텍스트 청킹 (문단 단위)
- `split_list_with_overlap(items, chunk_size, overlap_count)`: 리스트 청킹
- `merge_chunk_results(chunk_results, dedupe_key, merge_strategy)`: 결과 병합
- `calculate_chunk_progress(...)`: 청크별 진행률 계산

### 5.2 결과 병합 전략

**`merge_chunk_results()` 전략:**
- **"union"** (기본): 모든 결과 합치기 (중복 제거)
- **"intersection"**: 모든 청크에 공통으로 나타나는 결과만
- **"append"**: 단순 연결 (중복 제거만)

**중복 제거 키:**
- User Stories: `role:action:benefit`
- Bounded Contexts: `key`, `name`, 또는 `id`
- Commands/Events/Aggregates: `name` 또는 `id`
- Policies: `name` 또는 `id`

---

## 6. 성능 최적화

### 6.1 병렬 처리 효과

**이전 (순차 처리):**
- User Story 332개: ~30분
- Command 30개: ~2-30분

**현재 (병렬 처리):**
- User Story 332개: 병렬 처리로 대폭 단축
- Command 30개: 병렬 처리로 대폭 단축

### 6.2 타임아웃 보장

**모든 외부 호출에 타임아웃 적용:**
- LLM 호출: 5분 타임아웃
- Neo4j 생성: 10초 타임아웃
- Neo4j 연결: 5초 타임아웃

**블로킹 방지:**
- `asyncio.to_thread`로 동기 작업을 비동기로 변환
- `asyncio.wait_for`로 명시적 타임아웃 적용
- 에러 발생 시에도 다음 요소 처리 계속

### 6.3 로그 최적화

**로그 정책:**
- 모든 `print()` 문 제거
- `INFO`/`WARN` 레벨 로그 제거
- `ERROR` 레벨 로그만 유지
- 각 phase 종료 시 생성 결과 요약만 출력

---

## 7. 진행 상황 업데이트

### 7.1 Phase별 진행 범위

| Phase | 시작 | 종료 | 범위 |
|-------|------|------|------|
| `EXTRACTING_USER_STORIES` | 10 | 20 | 10% |
| `IDENTIFYING_BC` | 20 | 30 | 10% |
| `EXTRACTING_AGGREGATES` | 30 | 45 | 15% |
| `EXTRACTING_COMMANDS` | 45 | 60 | 15% |
| `EXTRACTING_EVENTS` | 60 | 75 | 15% |
| `IDENTIFYING_POLICIES` | 75 | 85 | 10% |
| `GENERATING_GWT` | 85 | 95 | 10% |
| `SAVING` | 95 | 100 | 5% |

### 7.2 청킹 시 진행 상황 업데이트

**패턴:**
1. Phase 시작: 시작 진행률
2. 스캐닝: 시작 + 1%
3. 청킹 완료: 시작 + 2%
4. 각 청크 처리: 청크 수에 따라 분배
5. 결과 병합: 종료 - 3%
6. Phase 완료: 종료 진행률

---

## 8. 주의사항

### 8.1 Traceability 유지
- 각 청크 결과에 원본 위치 정보 보존
- User Story ID, 참조 정보 등 추적 정보 유지

### 8.2 일관성 보장
- 청크 간 결과 일관성 검증
- 중복 제거 시 우선순위 결정 (첫 번째 청크 우선)

### 8.3 에러 처리
- 일부 청크 실패 시에도 나머지 청크 처리 계속
- `return_exceptions=True`로 예외를 결과로 반환
- 부분 실패 결과도 병합 (사용자에게 알림)

### 8.4 취소 처리
- 각 청크 처리 전 `ctx.session.is_cancelled` 확인
- 취소 시 즉시 중단 및 에러 이벤트 반환

---

## 9. 향후 개선 사항

1. **동적 청크 크기 조정**: LLM 응답 속도에 따라 청크 크기 조정
2. **병렬 청크 처리**: 독립적인 청크는 병렬 처리 고려
3. **캐싱**: 동일한 청크 재처리 방지
4. **프로그레스 추적**: 청크별 진행 상황 실시간 업데이트 개선
