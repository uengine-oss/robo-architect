# Model Modifier 아키텍처

## 1. 개요

Model Modifier는 Event Storming 도메인 모델을 채팅 기반으로 수정하는 기능입니다. 사용자가 캔버스에서 객체를 선택하고 자연어로 수정 요청을 하면, ReAct 패턴을 사용하여 영향도 분석을 수행하고 변경사항을 제안합니다.

### 1.1 핵심 기능
- **채팅 기반 수정**: 자연어로 도메인 모델 수정 요청
- **영향도 분석**: 선택된 노드의 변경이 다른 노드에 미치는 영향 자동 분석
- **ReAct 패턴**: Thought → Action → Observation 루프로 추론 과정 시각화
- **변경사항 승인**: 제안된 변경사항을 선택적으로 승인하여 적용

### 1.2 주요 구성 요소
1. **Frontend (Vue.js)**: 채팅 UI, 상태 관리, 변경사항 승인 UI
2. **Backend (FastAPI)**: SSE 스트리밍, ReAct 처리, 영향도 분석
3. **영향도 분석 엔진**: Neo4j 그래프 탐색 + LLM 기반 전파
4. **변경 적용 엔진**: 원자적 트랜잭션 기반 변경사항 적용

---

## 2. 전체 흐름

```
[사용자] 캔버스에서 노드 선택
    ↓
[Frontend] ChatPanel에서 수정 요청 입력
    ↓
[Backend] /api/chat/modify (SSE 스트리밍)
    ↓
[Backend] Intent 분석 (scope, required_types, need_propagation)
    ↓
[Backend] 영향도 전파 (propagate_impacts_node)
    ├─ Neo4j: 2-hop 서브그래프 조회
    └─ LLM: 영향받는 노드 후보 추천
    ↓
[Backend] 컨텍스트 주입 (선택 노드 + 전파된 노드)
    ↓
[Backend] ReAct 스트리밍 (LLM)
    ├─ THOUGHT: 변경 필요성 분석
    ├─ ACTION: 구체적 액션 제안
    ├─ OBSERVATION: 결과 예측
    └─ JSON 블록: DraftChange 제안
    ↓
[Frontend] DraftChange 수신 및 표시
    ↓
[사용자] 변경사항 선택 및 승인
    ↓
[Backend] /api/chat/confirm (원자적 적용)
    └─ Neo4j 트랜잭션으로 모든 변경사항 적용
```

---

## 3. Frontend 구조

### 3.1 주요 파일

#### `modelModifier.store.js` (Pinia Store)
**역할**: Model Modifier의 상태 관리

**주요 상태:**
- `messages`: 채팅 메시지 히스토리
- `selectedNodes`: 선택된 노드 (Design viewer 외)
- `isProcessing`: 처리 중 여부
- `reactTrace`: ReAct 추론 과정
- `appliedChanges`: 적용된 변경사항

**주요 함수:**
- `sendMessage(content)`: 수정 요청 전송
- `processModificationRequest(prompt, selectedNodes)`: SSE 스트리밍 처리
- `confirmDrafts(messageId)`: 승인된 변경사항 적용
- `toggleDraftApproval(messageId, changeId, approved)`: 개별 변경사항 승인/거부

#### `ChatPanel.vue` (UI 컴포넌트)
**역할**: 채팅 UI 및 변경사항 승인 UI

**주요 기능:**
- 선택된 노드를 칩으로 표시
- ReAct 추론 과정 (THOUGHT/ACTION/OBSERVATION) 표시
- DraftChange 목록 및 before/after diff 표시
- 영향도 요약 및 상세 보기 모달 열기

#### `ImpactDetailsModal.vue` (모달)
**역할**: 영향도 분석 상세 정보 표시

**주요 기능:**
- K-hop 영향도 그래프 시각화
- Propagation confirmed/review 노드 표시
- UserStory 영향도 조회
- 노드별 Properties 및 REFERENCES 표시

### 3.2 Inspector 통합

**CanvasWorkspace.vue**에서:
- 오른쪽 사이드바에 ChatPanel과 InspectorPanel을 토글 가능
- InspectorPanel에서 "채팅으로 수정 요청" 버튼으로 ChatPanel로 전환
- 두 패널은 동일한 선택된 노드 컨텍스트 공유

---

## 4. Backend 구조

### 4.1 API 엔드포인트

#### `POST /api/chat/modify` (SSE 스트리밍)
**역할**: 수정 요청 처리 및 ReAct 스트리밍 응답

**요청:**
```json
{
  "prompt": "이 Command의 이름을 변경하고 관련 Event도 업데이트해줘",
  "selectedNodes": [
    {
      "id": "...",
      "name": "...",
      "type": "Command",
      "bcId": "...",
      ...
    }
  ],
  "conversationHistory": [...]
}
```

**응답 (SSE 이벤트):**
- `impact_summary`: 영향도 분석 결과
- `thought`: 추론 과정
- `action`: 액션 제안
- `observation`: 결과 예측
- `draft_change`: 변경사항 제안 (JSON 블록)
- `draft_complete`: 모든 제안 완료

#### `POST /api/chat/confirm`
**역할**: 승인된 변경사항을 원자적으로 적용

**요청:**
```json
{
  "drafts": [DraftChange, ...],
  "approvedChangeIds": ["chg-...", ...]
}
```

**응답:**
```json
{
  "success": true,
  "appliedChanges": [...],
  "errors": []
}
```

#### `POST /api/chat/impact-details`
**역할**: K-hop 영향도 그래프 조회

**요청:**
```json
{
  "seedIds": ["node-id-1", "node-id-2"]
}
```

**응답:**
```json
{
  "k": 2,
  "whitelist": ["TRIGGERS", "INVOKES", ...],
  "hopGraph": {
    "nodes": [...],
    "relationships": [...]
  },
  "hopDistanceById": {...},
  "propertiesByParentId": {...},
  "propertyNodes": [...]
}
```

#### `GET /api/chat/node/{node_id}`
**역할**: 노드 상세 정보 조회

### 4.2 핵심 모듈

#### `react_streaming.py`
**역할**: ReAct 패턴 스트리밍 처리

**주요 함수:**
- `stream_react_response(prompt, selected_nodes, conversation_history)`: 메인 스트리밍 함수

**처리 단계:**
1. **Intent 분석**: LLM으로 요청의 scope, required_types, need_propagation 분석
2. **영향도 전파**: `propagate_impacts_node()` 호출하여 영향받는 노드 확장
3. **컨텍스트 주입**: 선택 노드 + 전파된 노드의 Properties 포함하여 컨텍스트 블록 생성
4. **ReAct 스트리밍**: LLM이 THOUGHT/ACTION/OBSERVATION 형식으로 응답
5. **JSON 블록 파싱**: DraftChange 제안 추출 및 before/after 정보 보강

#### `model_change_application.py`
**역할**: 변경사항 검증 및 적용

**주요 함수:**
- `apply_confirmed_changes_atomic(approved_changes)`: 원자적 적용

**처리 단계:**
1. **검증**: 각 변경사항의 action, targetId, updates 유효성 검사
2. **Property ID 해결**: Property의 경우 (parentType, parentId, name)으로 UUID 해결
3. **트랜잭션 적용**: Neo4j 트랜잭션으로 모든 변경사항 원자적 적용
4. **에러 처리**: 검증 실패 시 롤백 및 에러 반환

**지원하는 Action:**
- `rename`: 노드 이름 변경
- `update`: 노드 속성 업데이트 (description, template, Property 필드 등)
- `create`: 새 노드 생성 (Command, Event, Policy, UI, Property)
- `delete`: 노드 삭제 (soft delete 또는 Property는 hard delete)
- `connect`: 관계 생성 (TRIGGERS, INVOKES, EMITS, REFERENCES)

#### `react_prompt.py`
**역할**: ReAct 시스템 프롬프트 정의

**주요 내용:**
- 노드 타입 설명 (Command, Event, Policy, Aggregate, BoundedContext, UI, Property)
- 액션 타입 설명 (rename, update, create, delete, connect)
- Property 규칙 (parentType/parentId 필수, rename은 update 사용)
- UI wireframe 템플릿 표준 (HTML fragment, wf-root 클래스, 스타일 스코핑)

#### `react_sections.py`
**역할**: ReAct 응답에서 섹션 추출

**주요 함수:**
- `extract_section(text, section_name)`: THOUGHT/ACTION/OBSERVATION/SUMMARY 섹션 추출

#### `sse_events.py`
**역할**: SSE 이벤트 포맷팅

**주요 함수:**
- `format_sse_event(event_type, data)`: SSE 형식으로 이벤트 포맷팅

---

## 5. 영향도 분석

### 5.1 영향도 전파 엔진

**파일**: `api/features/change_management/planning_agent/impact_propagation_engine.py`

**주요 함수:**
- `propagate_impacts_node(state)`: 반복적으로 영향받는 노드 후보 확장

**처리 단계:**
1. **Seed 노드**: 선택된 노드를 초기 seed로 설정
2. **2-hop 서브그래프 조회**: Neo4j에서 relationship whitelist 기반 2-hop 이내 노드 조회
3. **LLM 기반 전파**: 각 라운드마다 LLM이 영향받을 가능성이 있는 노드 추천
4. **Confidence 필터링**: confidence 임계값 이상인 노드를 confirmed, 미만은 review로 분류
5. **라운드 반복**: max_rounds까지 반복하거나 새로운 후보가 없을 때까지

**설정:**
- `propagation_limits()`: max_rounds, max_candidates_per_round, confidence_threshold
- `relationship_whitelist()`: 영향도 분석에 사용할 관계 타입 목록

### 5.2 Neo4j 컨텍스트 조회

**파일**: `api/features/change_management/planning_agent/impact_propagation_neo4j_context.py`

**주요 함수:**
- `get_node_contexts(session, node_ids)`: 노드의 BC 컨텍스트 조회
- `fetch_2hop_subgraph(session, node_id, rel_types)`: 2-hop 서브그래프 조회

### 5.3 영향도 상세 조회

**파일**: `api/features/model_modifier/routes/chat_impact_details.py`

**주요 기능:**
- K-hop 그래프 조회 (K는 propagation max_rounds와 동일)
- Hop distance 계산 (seed로부터의 최소 거리)
- Properties by parent 조회
- BC 컨텍스트 부착

---

## 6. 변경사항 적용

### 6.1 DraftChange 구조

```typescript
interface DraftChange {
  changeId: string
  action: "rename" | "update" | "create" | "delete" | "connect"
  targetId: string
  targetName?: string
  targetType?: string
  bcId?: string
  rationale?: string
  updates?: {
    description?: string
    template?: string
    name?: string
    type?: string
    isKey?: boolean
    isForeignKey?: boolean
    isRequired?: boolean
    parentType?: string
    parentId?: string
    ...
  }
  before?: {...}  // 서버에서 보강
  after?: {...}   // 서버에서 보강
}
```

### 6.2 검증 규칙

**공통 검증:**
- `action` 필수
- `targetId` 필수 (Property는 예외, selector로 해결 가능)
- `rename`은 `targetName` 필수
- `update`/`create`는 `updates` 객체 필수

**타입별 검증:**
- **Property**: `parentType`, `parentId` 필수, `parentType`/`parentId` 변경 불가
- **UI**: `template`은 HTML fragment, wf-root 클래스 필수
- **일반 노드**: 허용된 필드만 업데이트 가능 (whitelist 기반)

**필드 길이 제한:**
- `name`: 200자
- `description`: 4000자
- `template`: 50000자

### 6.3 적용 로직

**트랜잭션 기반:**
- 모든 변경사항을 단일 Neo4j 트랜잭션으로 적용
- 검증 실패 시 롤백
- 적용 성공 시 커밋

**Property 특수 처리:**
- Property는 `(parentType, parentId, name)` 조합으로 고유 식별
- `targetId`가 없으면 유사도 기반 매칭 (Jaro-Winkler + Levenshtein)
- `rename`은 `update`로 처리 (`updates.name` 사용)

**UI Template 정규화:**
- HTML fragment로 정규화 (DOCTYPE, html, head, body 제거)
- wf-root 클래스 추가
- 스타일 스코핑 (`.wf-root` 하위로 제한)
- 스크립트 및 인라인 이벤트 핸들러 제거

---

## 7. 데이터 흐름

### 7.1 수정 요청 흐름

```
[Frontend] sendMessage()
    ↓
[Frontend] processModificationRequest()
    ↓ POST /api/chat/modify
[Backend] chat_modify.py::modify_nodes()
    ↓
[Backend] react_streaming.py::stream_react_response()
    ├─ Intent 분석 (LLM)
    ├─ 영향도 전파 (propagate_impacts_node)
    ├─ 컨텍스트 주입
    └─ ReAct 스트리밍 (LLM)
        ↓ SSE 이벤트 스트리밍
[Frontend] SSE 이벤트 수신 및 처리
    ├─ impact_summary → impactSummary 저장
    ├─ thought/action/observation → reactSteps 업데이트
    ├─ draft_change → drafts 배열에 추가
    └─ draft_complete → 최종 메시지 업데이트
```

### 7.2 변경사항 승인 흐름

```
[Frontend] 사용자가 DraftChange 승인/거부
    ↓
[Frontend] confirmDrafts()
    ↓ POST /api/chat/confirm
[Backend] chat_confirm.py::confirm_changes()
    ↓
[Backend] model_change_application.py::apply_confirmed_changes_atomic()
    ├─ 검증 (validate)
    ├─ Property ID 해결 (필요 시)
    └─ 트랜잭션 적용 (apply)
        ↓
[Backend] 응답 반환 (appliedChanges, errors)
    ↓
[Frontend] 적용 결과 표시 및 캔버스 동기화
```

### 7.3 영향도 상세 조회 흐름

```
[Frontend] ImpactDetailsModal 열기
    ↓
[Frontend] fetchHopDetails()
    ↓ POST /api/chat/impact-details
[Backend] chat_impact_details.py::impact_details()
    ├─ K-hop 그래프 조회 (Neo4j)
    ├─ Hop distance 계산
    ├─ Properties 조회
    └─ BC 컨텍스트 부착
        ↓
[Frontend] 영향도 그래프 시각화
```

---

## 8. 주요 설계 결정

### 8.1 ReAct 패턴 사용
- **이유**: LLM의 추론 과정을 투명하게 보여주고, 사용자가 변경사항의 근거를 이해할 수 있음
- **구현**: THOUGHT/ACTION/OBSERVATION 섹션을 스트리밍으로 실시간 표시

### 8.2 Draft-Apply 패턴
- **이유**: 사용자가 변경사항을 검토하고 선택적으로 승인할 수 있음
- **구현**: DraftChange를 제안하고, 승인된 것만 원자적으로 적용

### 8.3 영향도 전파
- **이유**: 선택된 노드의 변경이 다른 노드에 미치는 영향을 자동으로 분석
- **구현**: Neo4j 그래프 탐색 + LLM 기반 추론으로 영향받는 노드 후보 확장

### 8.4 원자적 적용
- **이유**: 여러 변경사항을 일관성 있게 적용하고, 실패 시 롤백
- **구현**: Neo4j 트랜잭션으로 모든 변경사항을 단일 트랜잭션으로 적용

### 8.5 Property 특수 처리
- **이유**: Property는 노드가 아닌 부모 노드의 임베디드 속성
- **구현**: (parentType, parentId, name) 조합으로 식별, 유사도 기반 매칭

---

## 9. 대용량 그래프 처리 현황 및 개선 방안

### 9.1 현재 구현의 제한사항

**영향도 전파 엔진:**
- `max_rounds`: 4 (기본값)
- `max_confirmed_nodes`: 60 (기본값)
- `max_new_per_round`: 20 (기본값)
- `max_frontier_per_round`: 8 (기본값)
- `format_subgraph_for_prompt`: 각 서브그래프를 `max_nodes=60`, `max_rels=120`으로 제한

**Model Modifier 컨텍스트:**
- `MODEL_MODIFIER_CONTEXT_CHARS_LIMIT`: 100,000자 (기본값)
- 초과 시 LLM으로 relevance ranking 수행하여 상위 노드만 선택

### 9.2 잠재적 문제점

**1. 2-hop 서브그래프 조회 시 제한 없음**
- `fetch_2hop_subgraph()`는 제한 없이 모든 2-hop 이내 노드와 관계를 조회
- 대용량 그래프(1000k 요구사항 → 300+ 노드)에서:
  - 하나의 노드만 선택해도 2-hop에 수백 개의 노드가 포함될 수 있음
  - 여러 frontier 노드(최대 8개)의 서브그래프를 합치면 수천 개의 노드가 될 수 있음

**2. 프롬프트 크기 제한 부족**
- `format_subgraph_for_prompt`에서 각 서브그래프를 60/120으로 제한하지만:
  - 여러 frontier 노드의 서브그래프를 합치면 여전히 클 수 있음
  - LLM 프롬프트 크기 제한이 없어 토큰 오버플로우 가능

**3. Neo4j 쿼리 성능**
- 2-hop 서브그래프 조회가 대용량 그래프에서 느릴 수 있음
- 여러 frontier 노드에 대해 순차적으로 쿼리 실행

### 9.3 개선 방안

#### 방안 1: 2-hop 서브그래프 조회 시 제한 추가
```python
def fetch_2hop_subgraph(
    session, 
    node_id: str, 
    rel_types: List[str],
    max_nodes: int = 200,  # 추가
    max_rels: int = 400     # 추가
) -> Dict[str, Any]:
    # 쿼리 결과를 LIMIT으로 제한하거나
    # 결과를 받은 후 슬라이싱
```

**장점:**
- Neo4j 쿼리 결과 크기 제한
- 메모리 사용량 감소

**단점:**
- 중요한 노드가 제외될 수 있음
- 제한된 노드만으로 영향도 분석이 부정확할 수 있음

#### 방안 2: 프롬프트 크기 제한 및 청킹
```python
def format_subgraph_for_prompt(
    center_id: str, 
    subgraph: Dict[str, Any], 
    max_nodes: int = 60, 
    max_rels: int = 120,
    max_chars: int = 5000  # 추가: 프롬프트 크기 제한
) -> str:
    # 노드/관계를 우선순위에 따라 정렬 후 선택
    # 또는 여러 서브그래프를 청크로 나누어 처리
```

**장점:**
- LLM 프롬프트 크기 제어
- 토큰 오버플로우 방지

**단점:**
- 구현 복잡도 증가
- 청크 간 컨텍스트 손실 가능

#### 방안 3: 배치 처리 및 병렬화
```python
# 여러 frontier 노드의 서브그래프를 병렬로 조회
async def fetch_subgraphs_parallel(
    session,
    node_ids: List[str],
    rel_types: List[str]
) -> List[Dict[str, Any]]:
    tasks = [
        asyncio.to_thread(fetch_2hop_subgraph, session, nid, rel_types)
        for nid in node_ids
    ]
    return await asyncio.gather(*tasks)
```

**장점:**
- 쿼리 성능 향상
- 대용량 그래프에서도 응답 시간 단축

**단점:**
- Neo4j 세션 관리 복잡도 증가
- 동시 쿼리로 인한 부하 증가 가능

#### 방안 4: 스마트 필터링 (우선순위 기반)
```python
def fetch_2hop_subgraph_with_priority(
    session,
    node_id: str,
    rel_types: List[str],
    priority_relationships: List[str] = ["TRIGGERS", "INVOKES", "EMITS"]  # 우선순위 관계
) -> Dict[str, Any]:
    # 1-hop은 모두 포함
    # 2-hop은 priority_relationships만 포함
    # 또는 노드 타입별 우선순위 (Policy > Command > Event > ...)
```

**장점:**
- 중요한 노드는 포함하면서 크기 제한
- 영향도 분석 정확도 유지

**단점:**
- 우선순위 로직 구현 필요
- 일부 노드가 누락될 수 있음

#### 방안 5: 점진적 확장 (현재 구조 개선)
```python
# 현재 구조를 유지하되 제한 강화
propagation_limits() -> Dict[str, Any]:
    return {
        "max_rounds": 3,  # 4 → 3으로 감소
        "max_confirmed_nodes": 40,  # 60 → 40으로 감소
        "max_new_per_round": 15,  # 20 → 15로 감소
        "max_frontier_per_round": 5,  # 8 → 5로 감소
        "max_nodes_per_subgraph": 50,  # 60 → 50으로 감소
        "max_rels_per_subgraph": 100,  # 120 → 100으로 감소
    }
```

**장점:**
- 구현 간단
- 기존 로직 유지

**단점:**
- 대용량 그래프에서 영향도 분석 범위 축소

### 9.4 권장 개선 사항

**단기 (즉시 적용 가능):**
1. ✅ **프롬프트 크기 제한 추가**: `format_subgraph_for_prompt`에 `max_chars` 파라미터 추가
2. ✅ **제한 값 조정**: 환경 변수로 제한 값 조정 가능하도록 (이미 구현됨)
3. ✅ **로깅 강화**: 서브그래프 크기, 프롬프트 크기 로깅

**중기 (구현 필요):**
1. **2-hop 서브그래프 조회 제한**: `fetch_2hop_subgraph`에 `max_nodes`, `max_rels` 파라미터 추가
2. **우선순위 기반 필터링**: 관계 타입 및 노드 타입별 우선순위 적용
3. **배치 처리**: 여러 frontier 노드의 서브그래프를 병렬로 조회

**장기 (아키텍처 개선):**
1. **청킹 전략**: 대용량 서브그래프를 청크로 나누어 LLM에 전달
2. **캐싱**: 동일한 노드의 2-hop 서브그래프 캐싱
3. **점진적 로딩**: 초기에는 1-hop만, 필요 시 2-hop 확장

---

## 10. 향후 개선 사항

1. **변경 히스토리**: 적용된 변경사항의 히스토리 관리 및 롤백 기능
2. **배치 적용**: 여러 메시지의 변경사항을 한 번에 승인/적용
3. **변경 미리보기**: 적용 전 변경사항의 시각적 미리보기
4. **충돌 해결**: 동시 수정 시 충돌 감지 및 해결 UI
5. **템플릿 라이브러리**: 자주 사용하는 수정 패턴을 템플릿으로 저장
6. **대용량 그래프 최적화**: 위 9.4 섹션의 개선 사항 적용