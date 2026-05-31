# Contract: BC & Aggregate Canvas (US3/US5)

진실의 원천=그래프. 캔버스 GET=투영 읽기, PATCH=속성만 SET(관계 보존, 034 D2), 자동생성=ddd-spec 재사용(SSE).

## Bounded Context Canvas — US3

### `GET /api/contexts/{bcId}/canvas`
- Res: `BcCanvasDTO` (purpose/classification/domainRoles/ubiquitousLanguage/inbound/outbound/businessDecisions/assumptions/version)
- inbound/outbound는 그래프 관계 투영(`BoundedContextProjection`).

### `PATCH /api/contexts/{bcId}/canvas`
- Req: `BcCanvasPatchRequest` (+`If-Match` 낙관적 버전) → 412 on mismatch.
- 속성만 SET; EMITS/INVOKES 등 관계 불변.

### `POST /api/ddd-spec/generate-bounded-context` (재사용)
- BC Canvas 자동생성 초안(렌더러 `bc_canvas.py`). 결과는 propose→confirm 후 PATCH로 반영.

## Aggregate Design Canvas — US5

### `GET /api/aggregates/{aggregateId}/canvas`
- Res: `AggregateCanvasDTO` (description/stateTransitions/commands/events/invariants/correctivePolicies/throughput/version)
- commands/events/invariants는 관계·spec 027 투영.

### `PATCH /api/aggregates/{aggregateId}/canvas`
- Req: `AggregateCanvasPatchRequest` (+`If-Match`). 속성만 SET.

### `POST /api/ddd-spec/generate-aggregate` (재사용)
- Aggregate Canvas 자동생성 초안(`aggregate_spec.py`).

## UI 배선
- **BcCanvasTab.vue**: `EpicDetail.vue`를 탭화하여 [Overview | Canvas | Clarify | AI편집 | History] 구성(UserStoryDetail 탭 패턴 재사용). 설계 캔버스 `CanvasWorkspace`에서 BC 노드 클릭 시(현재 무동작) `robo:switch-tab`+선택으로 EpicDetail Canvas 탭 오픈.
- **AggregateCanvasTab.vue**: `AggregateViewerInspector.vue`에 탭 슬롯 추가(spec 028 드릴다운 위). 상태전이는 Mermaid 렌더.
- 자동생성 버튼은 Settings `requirementGenerationEngine` 토글을 따르며 SSE 진행 표시; 미설치 시 설치 안내(FR-015).
