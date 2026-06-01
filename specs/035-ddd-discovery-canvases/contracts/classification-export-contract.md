# Contract: 전략 분류(3분류) & .ddd 내보내기 (US6/US7)

## Core/Supporting/Generic — US6 (`contexts` 확장)

### `GET /api/contexts/{bcId}/classification` (확장)
- Res: `{bcId, classification: "core"|"supporting"|"generic"|null}`

### `PATCH /api/contexts/{bcId}/classification` (확장)
- Req: `{classification}` (+`If-Match`) — Literal에 **generic 추가**, 가드 422.

### `POST /api/requirements/strategize/questions`
- 서브도메인/BC 목록에 분류 질문 산출.
- Res: `StrategizeQuestionDTO[]` ("외부 아웃소싱 시 고객이 알아챌까?" 등 ddd-starter Step4 휴리스틱).

### UI
- 컨텍스트 맵/BC Canvas에 분류 배지/색상(core=🔴, supporting=🟡, generic=⚪) — FR-023.

## .ddd 내보내기/가져오기 — US7

### `POST /api/requirements/ddd-export`
- Req: `DddExportRequest{outputDir?=".ddd", steps?[]}`
- 그래프 → `ddd_spec` 렌더러로 `.ddd/00-plan`~`08-aggregates/` 생성.
- Res: `DddExportResponse{writtenFiles[], skipped[]}`

### `POST /api/requirements/ddd-import/preview` (선택)
- `.ddd` 문서 변경 → diff.
- Res: `DddImportPreview{diffs: GraphChangePreview[]}`

### `POST /api/requirements/ddd-import/confirm` (선택)
- Req: `DddImportConfirmRequest{acceptedChangeIds[]}` — 확인 시에만 그래프 반영(FR-017/018). 충돌은 항목 안내.

## 재사용
- `ddd_spec` 렌더러(bc_canvas/aggregate_spec/context_map/domain_terms) — 출력 경로만 `.ddd/`로 매개변수화(research D11).
- 가져오기 반영은 `model_modifier` `apply_confirmed_changes_atomic`/change apply 재사용.

## 스키마 영향
- `BoundedContext.classification` 값 도메인 확장(라벨/관계 신설 없음). `docs/cypher/schema` 주석 보강.
