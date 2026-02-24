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
- **출력**: 없음 (단순 진행 이벤트)

### 2. User Stories Phase
- **파일**: `workflow/phases/user_stories.py`
- **프롬프트 위치**: `requirements_to_user_stories.py` (EXTRACT_USER_STORIES_PROMPT)
- **역할**: 요구사항 문서 → User Story 목록 추출
- **청킹**: 지원 (USER_STORY_CHUNK_SIZE = 14k 토큰)
- **중복 제거**: 정규화 기반 dedup (user_story_normalize.py)
- **출력**: `ctx.user_stories`

### 3. Bounded Contexts Phase
- **파일**: `workflow/phases/bounded_contexts.py`
- **프롬프트 위치**: `event_storming/prompts.py` (IDENTIFY_BC_FROM_STORIES_PROMPT)
- **역할**: User Stories → Bounded Context 식별 및 할당
- **청킹**: 지원 (30개 User Stories per chunk, overlap 3개)
- **출력**: `ctx.bounded_contexts`, User Story → BC 연결

### 4. Aggregates Phase
- **파일**: `workflow/phases/aggregates.py`
- **프롬프트 위치**: `event_storming/prompts.py` (EXTRACT_AGGREGATES_PROMPT)
- **역할**: BC별 Aggregate 식별
- **청킹**: 없음 (BC 단위로 처리)
- **출력**: `ctx.aggregates_by_bc`

### 5. Commands Phase
- **파일**: `workflow/phases/commands.py`
- **프롬프트 위치**: `event_storming/prompts.py` (EXTRACT_COMMANDS_PROMPT)
- **역할**: Aggregate별 Command 식별
- **청킹**: 지원 (User Story 텍스트 기반)
- **출력**: `ctx.commands_by_agg`

### 6. Events Phase
- **파일**: `workflow/phases/events.py`
- **프롬프트 위치**: `event_storming/prompts.py` (EXTRACT_EVENTS_PROMPT)
- **역할**: Command별 Event 식별
- **청킹**: 없음 (Aggregate 단위로 처리)
- **출력**: `ctx.events_by_agg`

### 7. ReadModels Phase
- **파일**: `workflow/phases/readmodels.py`
- **프롬프트 위치**: `event_storming/prompts.py` (EXTRACT_READMODELS_PROMPT)
- **역할**: BC별 ReadModel 식별
- **청킹**: 지원 (User Stories + Events 텍스트 기반)
- **출력**: `ctx.readmodels_by_bc`

### 8. Properties Phase
- **파일**: `workflow/phases/properties.py`
- **프롬프트 위치**: `event_storming/prompts.py` (GENERATE_PROPERTIES_AGGREGATE_BATCH_PROMPT, GENERATE_PROPERTIES_READMODELS_BATCH_PROMPT)
- **역할**: Aggregate/Command/Event/ReadModel 속성 생성
- **청킹**: 없음 (배치 단위로 처리)
- **출력**: Neo4j에 직접 저장

### 9. References Phase
- **파일**: `workflow/phases/references.py`
- **프롬프트**: 없음 (규칙 기반 자동 생성)
- **역할**: 외래키 참조 자동 생성
- **출력**: Neo4j에 직접 저장

### 10. Policies Phase
- **파일**: `workflow/phases/policies.py`
- **프롬프트 위치**: `event_storming/prompts.py` (IDENTIFY_POLICIES_PROMPT)
- **역할**: Event → Command Policy 식별
- **청킹**: 지원 (Events/Commands 텍스트 기반)
- **출력**: `ctx.policies`

### 11. GWT Phase
- **파일**: `workflow/phases/gwt.py`
- **프롬프트 위치**: `workflow/phases/gwt.py` (GENERATE_GWT_PROMPT_COMMAND, GENERATE_GWT_PROMPT_POLICY)
- **역할**: Command/Policy별 Given/When/Then 테스트 케이스 생성
- **청킹**: 지원 (8개 Commands per chunk)
- **출력**: Neo4j에 직접 저장

### 12. UI Wireframes Phase
- **파일**: `workflow/phases/ui_wireframes.py`
- **프롬프트 위치**: `workflow/phases/ui_wireframes.py` (_UI_WIREFRAME_SYSTEM_PROMPT)
- **역할**: Command/ReadModel별 UI Wireframe HTML 생성
- **청킹**: 없음 (Command/ReadModel 단위로 처리)
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

### 텍스트 기반 청킹:
- **User Stories**: 50k 토큰 (USER_STORY_CHUNK_SIZE)
- **Bounded Contexts**: 30개 User Stories (overlap 3개)
- **Commands**: User Story 텍스트 기반
- **ReadModels**: User Stories + Events 텍스트 기반
- **Policies**: Events/Commands 텍스트 기반

### 리스트 기반 청킹:
- **GWT**: 8개 Commands (overlap 1개, max_tokens 60k)

## 주요 유틸리티

- `workflow/utils/chunking.py`: 청킹 유틸리티
- `workflow/utils/user_story_normalize.py`: User Story 정규화 및 중복 제거
