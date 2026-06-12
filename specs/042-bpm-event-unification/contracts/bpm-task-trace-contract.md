# Contract: BPM Task Trace + Big picture 제거

## 1. `GET /api/graph/bpm-task/{task_id}/design-trace` (신규, 읽기 전용)

한 BPM task(`:BpmTask`)에 귀속된 UI·Command·Event·Policy·Aggregate·ReadModel 체인을 설계-궤적과 동일한 `{nodes, relationships}` 형태로 반환한다. BPM task 인스펙터의 "포함 요소" 모달이 소비.

### Request

| 항목 | 값 |
|---|---|
| Method | `GET` |
| Path | `/api/graph/bpm-task/{task_id}/design-trace` |
| Path param | `task_id` — `:BpmTask.id` |
| Query | `depth` (int, 기본 2, 1~5로 clamp) |
| Scope | `session_id` — 기존 세션 스코프 패턴(요청 컨텍스트) |
| Body | 없음 |

### Response 200 — `DesignTraceResponse` (기존 DTO 재사용)

```json
{
  "rootCommandId": "cmd_abc",   // task의 첫 루트 Command id, 없으면 null
  "nodes": [
    {"id": "cmd_abc", "type": "Command", "name": "...", "properties": [...]},
    {"id": "ui_1", "type": "UI", "name": "...", "properties": []},
    {"id": "evt_1", "type": "Event", "name": "...", "properties": [...]}
  ],
  "relationships": [
    {"source": "ui_1", "target": "cmd_abc", "type": "ATTACHED_TO"},
    {"source": "cmd_abc", "target": "evt_1", "type": "EMITS"}
  ],
  "empty": false
}
```

### Response 동작

| 상황 | 응답 |
|---|---|
| task 존재 + promoted Command ≥ 1 | 200, `empty:false`, 체인 노드/관계 |
| task 존재 + promoted Command 0 | 200, `empty:true`, `nodes:[]`, `relationships:[]` |
| task_id 미존재 | 404 `BpmTask {id} not found` |

### 불변 규칙 (계약 테스트 대상)

- **읽기 전용**: 어떤 그래프 변이도 없어야 한다(MERGE/CREATE/SET/DELETE 0).
- **신규 스키마 0건**: 쿼리는 기존 라벨/관계(`BpmTask`,`UserStory`,`Command`,`PROMOTED_TO`,`IMPLEMENTS`,`PROMOTED_FROM`,`ATTACHED_TO`,`EMITS`,`TRIGGERS`,`INVOKES`,`HAS_COMMAND`,`HAS_PROPERTY`)만 참조.
- **정합**: 반환 노드 집합 = 루트 Command(`(:BpmTask{id})-[:PROMOTED_TO]->(:UserStory)-[:IMPLEMENTS]->(:Command)` ∪ `(:Command)-[:PROMOTED_FROM]->(:BpmTask{id})`) 시드의 bounded 확장과 1:1(누락·과포함 0, SC-002). *라이브 검증 완료(세션 0dcf8cc7): task "결제수단별 처리 경로 결정" → nodes 5(UI·Command·Aggregate·Event×2).*
- **공유 로직**: user-story `design-trace`와 frontier-확장 코드를 공유(`_expand_trace`)하며, 기존 user-story 라우트 동작은 불변.

### 계약 테스트 (pytest)

1. 알려진 task → 200, 그 task의 Command/Event/UI가 노드에 등장.
2. promoted Command 0 task → `empty:true`.
3. 미존재 task_id → 404.
4. 호출 전/후 그래프 노드·관계 수 동일(읽기 전용).
5. `depth` 6 요청 → 5로 clamp.

---

## 2. 프런트 UI 계약 — BPM task 인스펙터 버튼 + 모달

| 항목 | 계약 |
|---|---|
| 위치 | `HybridTaskInspector.vue`에 "포함 요소 / 설계 궤적 보기" 버튼 |
| 동작 | 클릭 → `BpmTaskTraceModal.vue` 오픈 → 위 엔드포인트 fetch → `DesignTraceCanvas.vue`에 `:trace` 전달 |
| 재사용 | `DesignTraceCanvas.vue` **무수정**(이미 `trace` prop·`node-click` emit) |
| 캔버스 | **불변** — 모달은 오버레이, `bpmn-js`/`renderedFlows` 미접촉(FR-004) |
| empty | `trace.empty` → "이 task에 귀속된 설계 요소가 없습니다" 비차단 안내(US2 AC3) |
| 닫기 | 모달 닫으면 캔버스 상태 처음과 동일(US2 AC2) |

---

## 3. "Big picture" 제거 계약 (US4)

| 대상 | 조치 | 검증 |
|---|---|---|
| `App.vue` L6·L59 | import + `tabComponents` 항목 삭제 | 빌드 OK, 탭 없음 |
| `TopBar.vue` L4·L29·L108~114 | store import + 상태 표시 블록 삭제 | 상단바 정상 |
| `BigPicturePanel.vue` | 파일 삭제 | 참조 0 |
| `bigpicture.store.js` | 파일 삭제 | 참조 0 |
| `main.css` `.big-picture-panel` 등 | 관련 스타일 삭제 | 미사용 스타일 0 |
| `/api/graph/bigpicture-timeline` | 라우트 삭제(또는 비활성) | 호출처 0 |
| `TreeNode.vue` L33·L435·L613 | `'Big picture'` dead-branch + import 삭제 | 타 탭 노드추가 동작 불변 |
| `ExportDocumentTemplate.vue` L6·L10·L87 | swimlanes(빅픽처) 의존·섹션 제거 | export 정상 생성(D5-3) |

**불변 규칙**: 제거 후 `grep -ri "bigpicture\|big.picture\|BigPicture"` → 소스 0건(스타일 잔재 포함), 기존 뷰(BPM/Event Modeling/Requirements/Aggregate)·export·navigator 회귀 0건(SC-005).
