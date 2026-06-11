# Data Model: Proposal Impact Artifact Preview

**Feature**: `040-proposal-impact-preview` | **Date**: 2026-06-11

> 본 기능은 **신규 Neo4j 노드 라벨/관계/제약을 추가하지 않는다.** 미리보기 데이터는 039 `Proposal` 노드의 기존 직렬화 속성(`strategicDiff`/`tacticalDiff`/`impactMap`)에서 파생되는 **읽기 전용 투영**이다. 아래 모델은 런타임 합성 객체(Pydantic)와 프런트 상태이며 영속되지 않는다.

---

## 1. PreviewProjection (백엔드 런타임, Pydantic)

특정 Proposal · 뷰어 · 대상 노드에 대해 합성되는 읽기 전용 투영. 응답은 **대응 라이브 엔드포인트 형태를 미러**하며, 아래는 그 위에 얹는 메타이다.

```python
class PreviewSource(str, Enum):
    LIVE          = "live"           # 변경 없는 라이브 노드
    LIVE_MODIFIED = "live+modified"  # 라이브 + 제안의 MODIFY 오버레이
    TEMPORARY     = "temporary"      # 제안의 CREATE 신규 노드 (라이브 미존재)
    CONFLICT      = "conflict"       # MODIFY 대상이 라이브에 없음 (엣지)

class PreviewNodeMeta(BaseModel):
    nodeId: str                 # 라이브 id 또는 PREVIEW:<pid>:<idx>
    source: PreviewSource
    changedFields: list[str] = []   # MODIFY 시 변경된 필드 키
    badge: Optional[str] = None     # "신규" | "수정" | "충돌"

class PreviewEnvelope(BaseModel):
    proposalId: str
    viewer: str                 # "data" | "design" | "process" | "processes"
    targetNodeId: str           # 포커스할 노드 (라이브 id 또는 temp id)
    payload: dict               # 라이브 엔드포인트와 동일 형태의 본문 (+ source 태그)
    meta: list[PreviewNodeMeta] # 노드별 출처/배지
    renderable: bool = True     # False 면 프런트는 비활성 + reason 표시
    reason: Optional[str] = None
```

**검증 규칙**:
- `payload` 는 라이브 read 엔드포인트 스키마를 위반하지 않아야 한다(뷰어 파서 비파괴). `source` 는 노드 객체에 옵셔널 필드로 첨부.
- `targetNodeId` 는 항상 `payload`/`meta` 안에 존재해야 한다(포커스 보장, FR-003). 없으면 `renderable=false` + reason.
- 합성은 메모리 딥카피 위에서만. 어떤 필드도 Neo4j write 로 이어지지 않음(Constitution I).

---

## 2. Source 판정 규칙 (overlay_apply)

| 입력(diff 항목) | 라이브 존재 | source | badge |
|----------------|-----------|--------|-------|
| `changeType=MODIFY`, nodeId 매칭 | O | `live+modified` | 수정 |
| `changeType=MODIFY`, nodeId | X(삭제됨) | `conflict` | 충돌 |
| `changeType=CREATE`, nodeId=null | — | `temporary` | 신규 |
| diff 무관, impactMap 참조 노드 | O | `live` | — |

**임시 ID**: `CREATE` 항목에 `PREVIEW:<proposalId>:<index>` 부여. 제안 내 신규 노드 상호 참조(예: 신규 Command → 신규 Aggregate)는 제목 매칭으로 같은 temp ID 에 결선.

---

## 3. 오버레이 매핑 (뷰어별)

라이브 슬라이스 위에 어떤 diff 를 어떻게 얹는지.

### Data (Aggregate) — 라이브 BC full-tree + tacticalDiff
- `tacticalDiff[].semanticDiff.ops` 적용:
  - `obj_append`(valueObjects) → 해당 Aggregate 의 VO 목록에 신규 VO 추가(badge 신규).
  - `list_append`(invariants/properties) → 목록에 항목 추가(badge 수정).
  - `changeType=CREATE` Aggregate/Command/Event → BC 슬라이스에 신규 노드 삽입(temp id).
- 응답: `/api/contexts/{bcId}/full-tree` 와 동일 구조.

### Process (BPMN) — 라이브 process-flow + strategicDiff.processes
- `strategicDiff.processes[].fields.steps.after` 를 프로세스 단계 미리보기로 반영. 라이브 flow 없으면 텍스트 미리보기로 폴백.

### Design (UI) / Processes (Journey)
- 기본: impactMap 참조 라이브 노드를 읽기 전용 포커스(오버레이 없음, source=live).
- tacticalDiff 에 UI/이벤트모델 항목이 있으면 해당 뷰어 슬라이스에 오버레이(source=temporary/live+modified).

---

## 4. Frontend Preview State

### 뷰어 스토어 추가 상태 (도메인 중립)

```ts
previewSource: {
  baseUrl: string        // 예: `/api/proposals/PRO-001/preview`
  proposalId: string     // 배너 라벨용
  label: string          // "PRO-001"
  readOnly: true
} | null
```
- `setPreviewSource(src)` / `clearPreviewSource()`.
- fetch 분기: `previewSource ? ${baseUrl}/<live-path> : /api/<live-path>`.
- `readOnly` 동안 mutation 액션(addNode/deleteNode/createRelation/move*)은 **no-op + 콘솔 경고**(US2).

### 열기 라우팅 (OpenInViewerLink)

```ts
type OpenTarget = {
  viewer: 'data' | 'design' | 'process' | 'processes'  // nodeLabel→viewer 매핑
  targetNodeId: string
  bcId?: string          // Data 진입에 필요 시
}
// nodeLabel 매핑:
//   Aggregate|ValueObject|Enum|Command|Event → data
//   UI|Screen|UiFlow                         → design
//   Process|BpmnFlow                         → process
//   Journey|EventModel|ReadModel             → processes
//   (그 외/매핑 없음)                         → renderable=false, reason
```

### 앱 셸 오케스트레이션 (App.vue)

`robo:open-preview` 수신 → `activeTab = viewerToTab(viewer)` → 대상 store.`setPreviewSource(...)` → store.`focus<X>(targetNodeId)` → `PreviewBanner` 표시.

---

## 5. 미리보기 편집 → 제안 diff (US4)

미리보기 화면 편집(Inspector·Chat)은 라이브 그래프가 아니라 **Proposal 노드의 `tacticalDiff` 속성**에 반영된다.

- **정규화**: 편집된 Aggregate 의 deep 뷰(properties/enumerations/valueObjects/invariants/fields)를 해당 tacticalDiff 항목에 그대로 저장하고 `semanticDiff.ops` 는 비운다(중복 렌더 방지). 미리보기 전용 메타(`source`/`badge`)는 저장 전 제거.
- **대상 항목**: nodeId 일치 항목이 있으면 갱신, 없으면(라이브 Aggregate 첫 편집) `changeType=MODIFY` 항목 신규 생성.
- **Chat 적용**: 승인된 `DraftChange.after`/`updates` 를 동일 정규화 경로로 병합.
- **반환**: 편집 엔드포인트는 갱신된 미리보기 full-tree 를 돌려주고 뷰어가 즉시 교체 렌더.

## 6. 영속/스키마 영향

- **Neo4j 스키마 변경: 없음.** 신규 라벨/관계/제약/인덱스 0.
- **신규 영속 저장소: 없음.** 투영은 요청 시 합성.
- 원천 데이터: 039 `Proposal.strategicDiff/tacticalDiff/impactMap`(기존). 투영은 **읽기만**, 편집은 **`Proposal.tacticalDiff` 자기 속성만 쓰기**(라이브 디자인 그래프 무변경).
