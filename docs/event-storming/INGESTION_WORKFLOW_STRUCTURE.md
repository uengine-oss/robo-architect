# Ingestion Workflow 구조

## 전체 흐름

```
Requirements Text
    ↓
[1. Parsing Phase] - 문서 파싱 (프롬프트 없음, 단순 검증)
    ↓
[2. User Stories Phase] - 요구사항 → User Story 추출
    ↓
[3. User Story Sequencing Phase] - 비즈니스 흐름 순서 할당 (Event Modeling 타임라인 기준)
    ↓
[4. Events Phase (per UserStory)] - UserStory별 Event 추출 (Command 없이 독립 생성)
    ↓
[5. Bounded Contexts Phase] - User Stories → BC 식별 및 할당, BC↔Event 연결
    ↓
[6. Aggregates Phase] - BC별 Aggregate 식별
    ↓
[7. Commands Phase] - Aggregate별 Command 식별 + 기존 Event에 EMITS 링크
    ↓
[8. ReadModels Phase] - BC별 ReadModel 식별
    ↓
[9. Properties Phase] - Aggregate/Command/Event/ReadModel 속성 생성
    ↓
[10. References Phase] - 외래키 참조 생성 (프롬프트 없음, 규칙 기반)
    ↓
[11. Policies Phase] - Event → Command Policy 식별 (cross-BC 연결)
    ↓
[12. GWT Phase] - Command/Policy별 Given/When/Then 생성
    ↓
[13. UI Wireframes Phase] - Command/ReadModel별 UI 생성
    ↓
Complete
```

## Event Modeling 방식 핵심 변경

기존 Event Storming 방식과의 차이:

| 항목 | 기존 (Event Storming) | 현재 (Event Modeling) |
|---|---|---|
| **Event 추출 시점** | Command 이후 (step 6) | Command 이전 (step 4) |
| **Event 추출 기준** | Command별 추출 | **UserStory별 추출** |
| **Event 타임라인** | 없음 | UserStory sequence 기반 자동 할당 |
| **Command→Event 연결** | Command가 Event 생성 | Event 먼저 존재, Command가 `emits_event_names`로 연결 |
| **BC↔Event 연결** | 없음 | `UserStory→IMPLEMENTS→BC` + `UserStory→HAS_EVENT→Event` 경로로 자동 매핑 |

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

### 3. User Story Sequencing Phase
- **파일**: `workflow/phases/user_story_sequencing.py`
- **프롬프트 위치**: 동일 파일 (SEQUENCE_PROMPT)
- **역할**: 전체 UserStory에 비즈니스 흐름 순서(sequence) 할당
- **방식**: 요약본(역할+행위)만 LLM에 전달하여 토큰 절감
- **순서 기준**: 자연스러운 사용자 여정 (가입 → 인증 → 탐색 → 선택 → 주문 → 결제 → 배송 → 리뷰)
- **LLM 타임아웃**: 300s
- **출력**: `ctx.user_stories[].sequence` (Neo4j UserStory 노드에도 저장)
- **비고**: Event Modeling 타임라인의 X축 기준이 됨

### 4. Events Phase (per UserStory)
- **파일**: `workflow/phases/events_from_user_stories.py`
- **프롬프트 위치**: 동일 파일 (EXTRACT_EVENTS_FROM_US_PROMPT)
- **역할**: UserStory별 비즈니스 Event 독립 추출 (Command 없이)
- **청킹**: 없음 (UserStory 단위 1회 호출)
- **Event sequence**: UserStory의 sequence를 기반으로 Event에 자동 할당
- **Neo4j 관계**: `UserStory -[:HAS_EVENT]-> Event` 생성
- **LLM 타임아웃**: 300s
- **출력**: Neo4j Event 노드 직접 생성
- **비고**: 기존 `events.py` (Command별 추출) 대신 사용. Command는 이후 단계에서 기존 Event에 EMITS 연결
- **네이밍 규칙**: `name` 필드는 반드시 영문 PascalCase (한글/특수문자 금지). `displayName`에만 로컬라이즈 라벨. 실패 이벤트는 `성공이벤트명 stem + Failed` 패턴 (예: `OrderPlaced → OrderPlacementFailed`)

### 5. Bounded Contexts Phase
- **파일**: `workflow/phases/bounded_contexts.py`
- **프롬프트 위치**: `event_storming/prompts.py` (IDENTIFY_BC_FROM_STORIES_PROMPT)
- **역할**: User Stories → Bounded Context 식별 및 할당
- **청킹**: 지원 (30개 User Stories per chunk, overlap 3개)
  - 50개 이상이면 청킹 활성화 (should_chunk_list max_items=50)
  - 청크별 결과를 머지 후, 미할당 User Story에 대해 보정 LLM 호출
- **BC↔Event 자동 연결**: Phase 완료 시 `UserStory→IMPLEMENTS→BC` + `UserStory→HAS_EVENT→Event` 경로를 통해 `BC -[:HAS_EVENT]-> Event` 관계 자동 생성
- **LLM 타임아웃**: 300s (4곳: 청크별 BC 식별, 미할당 보정, 단일 패스, US 할당)
- **출력**: `ctx.bounded_contexts`, User Story → BC 연결 (IMPLEMENTS), BC → Event 연결 (HAS_EVENT)

### 6. Aggregates Phase
- **파일**: `workflow/phases/aggregates.py`
- **프롬프트 위치**: `event_storming/prompts.py` (EXTRACT_AGGREGATES_PROMPT)
- **역할**: BC별 Aggregate 식별
- **청킹**: 없음 (BC 단위로 1회 LLM 호출)
- **LLM 타임아웃**: 300s
- **출력**: `ctx.aggregates_by_bc`
- **비고**: Value Object 참조 검증 (이전 BC의 Aggregate 이름 기준)
- **SCOPE_EVENT 검증**: `covered_event_names` 매칭 결과가 0건이면 WARN 로그 (`ingestion.workflow.aggregates.scope_event_zero`)
- **조회전용 BC 가이드**: 프롬프트에 `query_only_bc` 섹션 — 조회만 하는 BC는 Aggregate를 0~1개로 제한 (CQRS Read side는 ReadModel만으로 충분)

### 7. Commands Phase
- **파일**: `workflow/phases/commands.py`
- **프롬프트 위치**: `event_storming/prompts.py` (EXTRACT_COMMANDS_PROMPT)
- **역할**: Aggregate별 Command 식별 + 기존 Event에 EMITS 링크
- **available_events 구성**: Neo4j에서 `name` + `displayName` 모두 조회하여 `- EventName  (displayName: 한글라벨)` 형태로 LLM에 전달 → 정확한 name 복사 유도
- **EMITS 연결** (4단계):
  1. LLM 응답의 `emits_event_names`로 이름 기반 fuzzy matching (`link_command_to_event_by_name`: name → displayName → case-insensitive)
  2. cross-BC EMITS 발생 시 WARN 로그 (차단하지 않음, 진단용)
  3. **EMITS 0건 시 BC-wide fuzzy 재시도**: 해당 BC의 전체 Event를 Neo4j에서 조회하여 substring 기반 재매칭 (LLM 재호출 없음)
  4. 재시도 후에도 0건이면 최종 WARN 로그 (`ingestion.workflow.commands.emits_zero_final`)
- **EMITS 검증**: 3개 초과 시 WARN 로그 (`ingestion.workflow.commands.emits_excessive`)
- **중복 검출**: `already_created_commands`에 displayName 포함 + Semantic Duplicate Detection 규칙 (프롬프트)
- **청킹**: 지원 (User Story 텍스트 기반, DEFAULT_CHUNK_SIZE=80k 토큰, overlap=2k)
  - should_chunk(full_prompt_text) → 100k 토큰 초과 시 활성화
- **LLM 타임아웃**: 300s
- **출력**: `ctx.commands_by_agg`

### 8. ReadModels Phase
- **파일**: `workflow/phases/readmodels.py`
- **프롬프트 위치**: `event_storming/prompts.py` (EXTRACT_READMODELS_PROMPT)
- **역할**: BC별 ReadModel 식별
- **청킹**: 지원 (User Stories + Events 텍스트 기반, DEFAULT_CHUNK_SIZE=80k 토큰)
  - User Stories와 Events 텍스트를 각각 독립적으로 청킹한 뒤 조합
- **LLM 타임아웃**: 300s
- **출력**: `ctx.readmodels_by_bc`
- **CQRS 미연결 이벤트 보고**: Phase 완료 후 `TRIGGERED_BY` 관계가 없고 `~Failed`로 끝나지 않는 Event 집계 → WARN 로그 (`ingestion.workflow.readmodels.cqrs_orphan_events`)

### 9. Properties Phase
- **파일**: `workflow/phases/properties.py`
- **프롬프트 위치**: `event_storming/prompts.py` (GENERATE_PROPERTIES_AGGREGATE_BATCH_PROMPT, GENERATE_PROPERTIES_READMODELS_BATCH_PROMPT)
- **역할**: Aggregate/Command/Event/ReadModel 속성 생성
- **청킹**: 없음 (BC별 Aggregate 배치 + BC별 ReadModel 배치)
- **LLM 타임아웃**: 300s (2곳: aggregate batch, readmodels batch)
- **출력**: Neo4j에 직접 저장 (upsert)

### 10. References Phase
- **파일**: `workflow/phases/references.py`
- **프롬프트**: 없음 (규칙 기반 자동 생성)
- **역할**: 외래키 참조 자동 생성
- **LLM 타임아웃**: N/A
- **출력**: Neo4j에 직접 저장

### 11. Policies Phase
- **파일**: `workflow/phases/policies.py`
- **프롬프트 위치**: `event_storming/prompts.py` (IDENTIFY_POLICIES_PROMPT)
- **역할**: Event → Command Policy(Automation) 식별
  - **cross-BC + same-BC 모두 허용**: Event Modeling 이론에서 Policy(Automation)는 "이벤트에 반응하여 시스템이 자동 트리거하는 Command"를 의미하며 BC 경계와 무관. same-BC 생성 시 INFO 로그
  - 프롬프트에서 cross-BC 우선 유도 (Mandatory cross-BC flow categories 체크리스트, N×(N-1) BC 쌍 전수 검토, 5개 미만 시 재검토 가이드)
- **이벤트 조회 전략** (3단계 fallback):
  1. Neo4j `BC -[:HAS_EVENT]-> Event` 직접 조회
  2. `ctx.events_by_agg` 기반 보충
  3. Neo4j 전체 Event 직접 조회 (`MATCH (evt:Event)`)
- **Command 조회 fallback**: `ctx.commands_by_agg` 미발견 시 Neo4j `BC→Aggregate→Command` 직접 조회
- **추가 컨텍스트**: `<commands_without_emits>` 섹션 — EMITS 없는 Command를 Policy invoke 후보로 제시
- **검증**: self-loop 제거, 2-hop 간접 cycle 감지, 중복 trigger→command 제거
- **후처리**:
  - invoke Command BC 소속 보장: `HAS_COMMAND` 관계 없는 orphan Command를 target BC의 Aggregate에 자동 연결
  - BC 고립 경고: outgoing Policy 0개이면서 Command를 보유한 BC 탐지 → WARN 로그
- **청킹**: 지원 (Events/Commands 텍스트 기반, DEFAULT_CHUNK_SIZE=80k 토큰)
- **LLM 타임아웃**: 300s
- **출력**: `ctx.policies`

### 12. GWT Phase
- **파일**: `workflow/phases/gwt.py`
- **프롬프트 위치**: `workflow/phases/gwt.py` (GENERATE_GWT_PROMPT_COMMAND, GENERATE_GWT_PROMPT_POLICY)
- **역할**: Command/Policy별 Given/When/Then 테스트 케이스 생성
- **청킹**: 지원 (8개 Commands per chunk, overlap 1개, max_tokens 60k)
- **LLM 타임아웃**: 300s
- **출력**: Neo4j에 직접 저장

### 13. UI Wireframes Phase
- **파일**: `workflow/phases/ui_wireframes.py`
- **프롬프트 위치**: `workflow/phases/ui_wireframes.py` (_UI_WIREFRAME_SYSTEM_PROMPT)
- **역할**: Command/ReadModel별 UI Wireframe HTML 생성
- **청킹**: 없음 (Command/ReadModel 단위로 처리)
- **LLM 타임아웃**: 300s
- **출력**: `ctx.uis`
- **비고**: `IS_SKIP_UI_PHASE` 환경변수로 생략 가능

## 프롬프트 위치 정리

### `event_storming/prompts.py`에 있는 프롬프트:
- `SYSTEM_PROMPT` - 공통 시스템 프롬프트
- `IDENTIFY_BC_FROM_STORIES_PROMPT` - BC 식별
- `EXTRACT_AGGREGATES_PROMPT` - Aggregate 추출
- `EXTRACT_COMMANDS_PROMPT` - Command 추출
- `EXTRACT_EVENTS_PROMPT` - Event 추출 (레거시, 현재 미사용)
- `EXTRACT_READMODELS_PROMPT` - ReadModel 추출
- `IDENTIFY_POLICIES_PROMPT` - Policy 식별
- `GENERATE_PROPERTIES_AGGREGATE_BATCH_PROMPT` - Aggregate 속성 생성
- `GENERATE_PROPERTIES_READMODELS_BATCH_PROMPT` - ReadModel 속성 생성

### 각 Phase 파일에 있는 프롬프트:
- `requirements_to_user_stories.py`: `EXTRACT_USER_STORIES_PROMPT`
- `workflow/phases/user_story_sequencing.py`: `SEQUENCE_PROMPT` (Event Modeling 신규)
- `workflow/phases/events_from_user_stories.py`: `EXTRACT_EVENTS_FROM_US_PROMPT` (Event Modeling 신규)
- `workflow/phases/gwt.py`: `GENERATE_GWT_PROMPT_COMMAND`, `GENERATE_GWT_PROMPT_POLICY`
- `workflow/phases/ui_wireframes.py`: `_UI_WIREFRAME_SYSTEM_PROMPT`

### 프롬프트 없는 Phase:
- `parsing.py` - 단순 검증
- `references.py` - 규칙 기반 자동 생성

### 유틸리티 (워크플로우 러너에서 직접 호출하지 않음):
- `workflow/phases/events.py` - 레거시 Command별 Event 추출 (현재 미사용)
- `workflow/phases/link_command_to_events.py` - Command→Event EMITS 링크 유틸리티 (일시정지/재개 시 ctx 동기화용)

## 데이터 흐름

```
ctx.content (원본 요구사항)
    ↓
ctx.user_stories (User Story 목록, sequence 포함)
    ↓
Neo4j: UserStory -[:HAS_EVENT]-> Event (UserStory별 Event, sequence 할당)
    ↓
ctx.bounded_contexts (BC 목록)
Neo4j: BC -[:HAS_EVENT]-> Event (자동 매핑)
    ↓
ctx.aggregates_by_bc (BC별 Aggregate)
    ↓
ctx.commands_by_agg (Aggregate별 Command)
Neo4j: Command -[:EMITS]-> Event (기존 Event에 연결)
    ↓
ctx.readmodels_by_bc (BC별 ReadModel)
    ↓
ctx.policies (Policy 목록)
Neo4j: Event -[:TRIGGERS]-> Policy -[:INVOKES]-> Command
    ↓
ctx.uis (UI 목록)
```

## Neo4j 관계 요약 (Event Modeling 기준)

```
UserStory -[:IMPLEMENTS]-> BoundedContext
UserStory -[:HAS_EVENT]-> Event
BoundedContext -[:HAS_EVENT]-> Event          (자동 매핑: US→BC + US→Event 경로)
BoundedContext -[:HAS_AGGREGATE]-> Aggregate
Aggregate -[:HAS_COMMAND]-> Command
Command -[:EMITS]-> Event                     (emits_event_names 기반 연결)
BoundedContext -[:HAS_READMODEL]-> ReadModel
ReadModel -[:HAS_CQRS]-> CQRSConfig -[:HAS_OPERATION]-> CQRSOperation -[:TRIGGERED_BY]-> Event
Event -[:TRIGGERS]-> Policy -[:INVOKES]-> Command  (cross-BC 프로세스 연결)
BoundedContext -[:HAS_POLICY]-> Policy
UI -[:ATTACHED_TO]-> Command | ReadModel
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
- **User Story Sequencing**: 전체 US 요약본 1회 호출
- **Events (per US)**: UserStory 단위 1회 호출
- **Aggregates**: BC 단위 1회 호출
- **Properties**: BC별 Aggregate 배치 + BC별 ReadModel 배치
- **UI Wireframes**: Command/ReadModel 단위 개별 호출

## LLM 타임아웃

모든 LLM 호출에 `asyncio.wait_for(timeout=300.0)` (5분) 적용:

| Phase | 타임아웃 | 비고 |
|---|---|---|
| Parsing | N/A | LLM 미사용 |
| User Stories | 내부 관리 | extract_user_stories_from_text |
| User Story Sequencing | 300s | 전체 US 1회 |
| Events (per US) | 300s | UserStory별 |
| Bounded Contexts | 300s | 4곳 (청크별, 보정, 단일패스, 할당) |
| Aggregates | 300s | BC별 1회 |
| Commands | 300s | 청크별, EMITS 링크 포함 |
| ReadModels | 300s | 청크별 |
| Properties | 300s | 2곳 (aggregate batch, readmodels batch) |
| References | N/A | LLM 미사용 |
| Policies | 300s | 청크별, 3단계 이벤트 fallback |
| GWT | 300s | 청크별 |
| UI Wireframes | 300s | Command/ReadModel별 |

## Command→Event 매핑 (Event Modeling 방식)

Event Modeling에서는 Event가 Command보다 먼저 생성됨. Command 생성 시 기존 Event에 연결:

1. **LLM 응답 매핑**: Command의 `emits_event_names` 필드로 Event name 기준 매칭
2. **Neo4j 이름 매칭**: `link_command_to_event_by_name` — name → displayName → case-insensitive fuzzy matching
3. **cross-BC EMITS 진단**: Command BC ≠ Event BC인 경우 WARN 로그 (차단하지 않음)
4. **EMITS 0건 BC-wide 재시도**: 1~2단계에서 0건이면 해당 BC 전체 Event를 Neo4j 조회 → substring 기반 fuzzy 재매칭 (LLM 재호출 없음)
5. **EMITS 관계 생성**: `Command -[:EMITS]-> Event` (Event 노드 재생성 없음)

> 기존 Event Storming 방식 (레거시):
> 1. 명시적 매핑: Event의 `emitting_command_name` 필드로 Command name 매칭
> 2. 인덱스 기반 fallback: `events[i] ↔ commands[i]`
> 3. 최종 fallback: `commands[0]`에 연결

## 병렬 흐름 (Event Modeling API)

동일 Command가 EMITS하는 이벤트(성공/실패 분기)는 같은 타임라인 column에 배치:

- **API 처리** (`canvas_graph/routes/event_modeling.py` 3a-2 단계): 같은 Command가 EMITS하는 Event들의 `storedSequence`를 그룹 내 최소값으로 통일
- **프론트엔드**: 동일 sequence 카드를 Y축 스택 배치 (기존 `evtCardPos`, `cmdStackIndex` 로직 활용)
- 예: `PlaceOrder → OrderPlaced(seq=5) / OrderPlacementFailed(seq=6)` → 둘 다 seq=5, 같은 column 위아래

## 주요 유틸리티

- `workflow/utils/chunking.py`: 청킹 유틸리티
  - `USER_STORY_CHUNK_SIZE = 3000` (3k 토큰)
  - `DEFAULT_CHUNK_SIZE = 80000` (80k 토큰)
  - `DEFAULT_OVERLAP_SIZE = 2000` (2k 문자)
  - `DEFAULT_MAX_TOKENS = 100000` (should_chunk 임계값)
- `workflow/utils/user_story_normalize.py`: User Story 정규화 및 중복 제거
- `workflow/phases/link_command_to_events.py`: Command→Event EMITS 링크 유틸리티 (일시정지/재개 sync용)
