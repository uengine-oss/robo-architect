# Ingestion Workflow 구조

## 전체 흐름

```
Requirements Text
    ↓
[1. Parsing Phase] - 문서 파싱 (프롬프트 없음, 단순 검증)
    ↓
[2. User Stories Phase] - 요구사항 → User Story 추출
    ↓
[3. Bounded Contexts Phase] - User Stories → BC 식별 및 할당
    ↓
[4. Aggregates Phase] - BC별 Aggregate 식별
    ↓
[5. Commands Phase] - Aggregate별 Command 식별
    ↓
[6. Events Phase] - Command별 Event 식별
    ↓
[7. ReadModels Phase] - BC별 ReadModel 식별
    ↓
[8. Properties Phase] - Aggregate/Command/Event/ReadModel 속성 생성
    ↓
[9. References Phase] - 외래키 참조 생성 (프롬프트 없음, 규칙 기반)
    ↓
[10. Policies Phase] - Event → Command Policy 식별
    ↓
[11. GWT Phase] - Command/Policy별 Given/When/Then 생성
    ↓
[12. UI Wireframes Phase] - Command/ReadModel별 UI 생성
    ↓
Complete
```

## 각 Phase 상세

### 1. Parsing Phase
- **파일**: `workflow/phases/parsing.py`
- **프롬프트**: 없음 (단순 검증)
- **역할**: 문서 파싱 및 기본 검증
- **LLM 타임아웃**: N/A
- **출력**: 없음 (단순 진행 이벤트)

### 2. User Stories Phase
- **파일**: `workflow/phases/user_stories.py`
- **프롬프트 위치**: `requirements_to_user_stories.py` (EXTRACT_USER_STORIES_PROMPT)
- **역할**: 요구사항 문서 → User Story 목록 추출
- **청킹**: 지원 (USER_STORY_CHUNK_SIZE = 3k 토큰, 5% overlap)
  - 출력 안정성 기준 설계: completion cap 32,768 tokens 내에서 안전한 생성량 유지
  - 3k 입력 → 10~25 story 생성 (안전 범위)
  - 불완전 출력 감지: chunk_tokens ≥ 1800 && stories < 6이면 recursive split
  - 최대 동시 처리: 3개 chunk (max_concurrent=3)
- **중복 제거**: 정규화 기반 dedup (user_story_normalize.py)
- **LLM 타임아웃**: extract_user_stories_from_text 내부에서 관리
- **출력**: `ctx.user_stories`

### 3. Bounded Contexts Phase
- **파일**: `workflow/phases/bounded_contexts.py`
- **프롬프트 위치**: `event_storming/prompts.py` (IDENTIFY_BC_FROM_STORIES_PROMPT)
- **역할**: User Stories → Bounded Context 식별 및 할당
- **청킹**: 지원 (30개 User Stories per chunk, overlap 3개)
  - 50개 이상이면 청킹 활성화 (should_chunk_list max_items=50)
  - 청크별 결과를 머지 후, 미할당 User Story에 대해 보정 LLM 호출
- **LLM 타임아웃**: 300s (4곳: 청크별 BC 식별, 미할당 보정, 단일 패스, US 할당)
- **출력**: `ctx.bounded_contexts`, User Story → BC 연결

### 4. Aggregates Phase
- **파일**: `workflow/phases/aggregates.py`
- **프롬프트 위치**: `event_storming/prompts.py` (EXTRACT_AGGREGATES_PROMPT)
- **역할**: BC별 Aggregate 식별
- **청킹**: 없음 (BC 단위로 1회 LLM 호출)
- **LLM 타임아웃**: 300s
- **출력**: `ctx.aggregates_by_bc`
- **비고**: Value Object 참조 검증 (이전 BC의 Aggregate 이름 기준)

### 5. Commands Phase
- **파일**: `workflow/phases/commands.py`
- **프롬프트 위치**: `event_storming/prompts.py` (EXTRACT_COMMANDS_PROMPT)
- **역할**: Aggregate별 Command 식별
- **청킹**: 지원 (User Story 텍스트 기반, DEFAULT_CHUNK_SIZE=80k 토큰, overlap=2k)
  - should_chunk(full_prompt_text) → 100k 토큰 초과 시 활성화
- **LLM 타임아웃**: 300s
- **출력**: `ctx.commands_by_agg`

### 6. Events Phase
- **파일**: `workflow/phases/events.py`
- **프롬프트 위치**: `event_storming/prompts.py` (EXTRACT_EVENTS_PROMPT)
- **역할**: Command별 Event 식별
- **청킹**: 없음 (Aggregate 단위로 처리)
- **Command→Event 매핑**: `emitting_command_name` 필드로 명시적 매핑 (fallback: 인덱스 기반)
- **LLM 타임아웃**: 300s
- **출력**: `ctx.events_by_agg`

### 7. ReadModels Phase
- **파일**: `workflow/phases/readmodels.py`
- **프롬프트 위치**: `event_storming/prompts.py` (EXTRACT_READMODELS_PROMPT)
- **역할**: BC별 ReadModel 식별
- **청킹**: 지원 (User Stories + Events 텍스트 기반, DEFAULT_CHUNK_SIZE=80k 토큰)
  - User Stories와 Events 텍스트를 각각 독립적으로 청킹한 뒤 조합
- **LLM 타임아웃**: 300s
- **출력**: `ctx.readmodels_by_bc`

### 8. Properties Phase
- **파일**: `workflow/phases/properties.py`
- **프롬프트 위치**: `event_storming/prompts.py` (GENERATE_PROPERTIES_AGGREGATE_BATCH_PROMPT, GENERATE_PROPERTIES_READMODELS_BATCH_PROMPT)
- **역할**: Aggregate/Command/Event/ReadModel 속성 생성
- **청킹**: 없음 (BC별 Aggregate 배치 + BC별 ReadModel 배치)
- **LLM 타임아웃**: 300s (2곳: aggregate batch, readmodels batch)
- **출력**: Neo4j에 직접 저장 (upsert)

### 9. References Phase
- **파일**: `workflow/phases/references.py`
- **프롬프트**: 없음 (규칙 기반 자동 생성)
- **역할**: 외래키 참조 자동 생성
- **LLM 타임아웃**: N/A
- **출력**: Neo4j에 직접 저장

### 10. Policies Phase
- **파일**: `workflow/phases/policies.py`
- **프롬프트 위치**: `event_storming/prompts.py` (IDENTIFY_POLICIES_PROMPT)
- **역할**: Event → Command Policy 식별
- **청킹**: 지원 (Events/Commands 텍스트 기반, DEFAULT_CHUNK_SIZE=80k 토큰)
- **LLM 타임아웃**: 300s
- **출력**: `ctx.policies`

### 11. GWT Phase
- **파일**: `workflow/phases/gwt.py`
- **프롬프트 위치**: `workflow/phases/gwt.py` (GENERATE_GWT_PROMPT_COMMAND, GENERATE_GWT_PROMPT_POLICY)
- **역할**: Command/Policy별 Given/When/Then 테스트 케이스 생성
- **청킹**: 지원 (8개 Commands per chunk, overlap 1개, max_tokens 60k)
- **Command→Event 매핑**: `emitting_command_name` 필드로 명시적 매핑 (fallback: 인덱스 기반)
- **LLM 타임아웃**: 300s
- **출력**: Neo4j에 직접 저장

### 12. UI Wireframes Phase
- **파일**: `workflow/phases/ui_wireframes.py`
- **프롬프트 위치**: `workflow/phases/ui_wireframes.py` (_UI_WIREFRAME_SYSTEM_PROMPT)
- **역할**: Command/ReadModel별 UI Wireframe HTML 생성
- **청킹**: 없음 (Command/ReadModel 단위로 처리)
- **LLM 타임아웃**: 300s
- **출력**: `ctx.uis`

## 프롬프트 위치 정리

### `event_storming/prompts.py`에 있는 프롬프트:
- `SYSTEM_PROMPT` - 공통 시스템 프롬프트
- `IDENTIFY_BC_FROM_STORIES_PROMPT` - BC 식별
- `EXTRACT_AGGREGATES_PROMPT` - Aggregate 추출
- `EXTRACT_COMMANDS_PROMPT` - Command 추출
- `EXTRACT_EVENTS_PROMPT` - Event 추출
- `EXTRACT_READMODELS_PROMPT` - ReadModel 추출
- `IDENTIFY_POLICIES_PROMPT` - Policy 식별
- `GENERATE_PROPERTIES_AGGREGATE_BATCH_PROMPT` - Aggregate 속성 생성
- `GENERATE_PROPERTIES_READMODELS_BATCH_PROMPT` - ReadModel 속성 생성

### 각 Phase 파일에 있는 프롬프트:
- `requirements_to_user_stories.py`: `EXTRACT_USER_STORIES_PROMPT`
- `workflow/phases/gwt.py`: `GENERATE_GWT_PROMPT_COMMAND`, `GENERATE_GWT_PROMPT_POLICY`
- `workflow/phases/ui_wireframes.py`: `_UI_WIREFRAME_SYSTEM_PROMPT`

### 프롬프트 없는 Phase:
- `parsing.py` - 단순 검증
- `references.py` - 규칙 기반 자동 생성

## 데이터 흐름

```
ctx.content (원본 요구사항)
    ↓
ctx.user_stories (User Story 목록)
    ↓
ctx.bounded_contexts (BC 목록)
ctx.aggregates_by_bc (BC별 Aggregate)
ctx.commands_by_agg (Aggregate별 Command)
ctx.events_by_agg (Aggregate별 Event)
ctx.readmodels_by_bc (BC별 ReadModel)
ctx.policies (Policy 목록)
ctx.uis (UI 목록)
```

## 청킹 전략

### 텍스트 기반 청킹 (split_text_with_overlap):
- **User Stories**: 3k 토큰 (USER_STORY_CHUNK_SIZE), 5% overlap
  - 출력 안정성 기준: completion cap 32,768 tokens 대비 안전한 입력 크기
- **Commands**: 80k 토큰 (DEFAULT_CHUNK_SIZE), 2k 문자 overlap
  - 100k 토큰 초과 시 활성화
- **ReadModels**: 80k 토큰, User Stories + Events 각각 독립 청킹
- **Policies**: 80k 토큰, Events/Commands 텍스트 기반

### 리스트 기반 청킹 (split_list_with_overlap):
- **Bounded Contexts**: 30개 User Stories per chunk, overlap 3개
- **GWT**: 8개 Commands per chunk, overlap 1개, max_tokens 60k

### 청킹 없는 Phase:
- **Aggregates**: BC 단위 1회 호출
- **Events**: Aggregate 단위 1회 호출
- **Properties**: BC별 Aggregate 배치 + BC별 ReadModel 배치
- **UI Wireframes**: Command/ReadModel 단위 개별 호출

## LLM 타임아웃

모든 LLM 호출에 `asyncio.wait_for(timeout=300.0)` (5분) 적용:

| Phase | 타임아웃 | 비고 |
|---|---|---|
| Parsing | N/A | LLM 미사용 |
| User Stories | 내부 관리 | extract_user_stories_from_text |
| Bounded Contexts | 300s | 4곳 (청크별, 보정, 단일패스, 할당) |
| Aggregates | 300s | BC별 1회 |
| Commands | 300s | 청크별 |
| Events | 300s | Aggregate별 1회 |
| ReadModels | 300s | 청크별 |
| Properties | 300s | 2곳 (aggregate batch, readmodels batch) |
| References | N/A | LLM 미사용 |
| Policies | 300s | 청크별 |
| GWT | 300s | 청크별 |
| UI Wireframes | 300s | Command/ReadModel별 |

## Command→Event 매핑

Events Phase와 GWT Phase에서 Command↔Event 연결 시 사용하는 매핑 전략:

1. **명시적 매핑 (우선)**: Event의 `emitting_command_name` 필드로 Command name 기준 매칭
2. **인덱스 기반 fallback**: 명시적 매핑 실패 시 `events[i] ↔ commands[i]` 순서 매핑
3. **최종 fallback**: 인덱스 초과 시 `commands[0]`에 연결

## 주요 유틸리티

- `workflow/utils/chunking.py`: 청킹 유틸리티
  - `USER_STORY_CHUNK_SIZE = 3000` (3k 토큰)
  - `DEFAULT_CHUNK_SIZE = 80000` (80k 토큰)
  - `DEFAULT_OVERLAP_SIZE = 2000` (2k 문자)
  - `DEFAULT_MAX_TOKENS = 100000` (should_chunk 임계값)
- `workflow/utils/user_story_normalize.py`: User Story 정규화 및 중복 제거
