# Quickstart: Proposal Impact Artifact Preview

**Feature**: `040-proposal-impact-preview` | **Date**: 2026-06-11

039 Proposal Lifecycle 위에 "임팩트 항목 → 기존 뷰어로 열기(읽기 전용 오버레이 미리보기)"를 얹는 개발 가이드.

---

## 사전 조건

- 039 가 동작 중(Proposal 생성 + 인텐트 분해로 `strategicDiff`/`tacticalDiff`/`impactMap` 보유).
- 백엔드: `uvicorn api.main:app --reload --host 127.0.0.1 --port 8000`
- 프런트: `cd frontend && npm run dev`
- Neo4j 라이브 그래프에 결제/환불 같은 BC·Aggregate 시드 존재(오버레이 대상).

---

## 백엔드 구현 순서

1. **`services/preview_projection.py`** — `build_preview_for_target(proposal_id, viewer, target_node_id)`:
   - 039 `ProposalResponse.from_neo4j` 로 diff 로드.
   - `read_live_slice(viewer, target)` — **read 트랜잭션 전용**으로 라이브 슬라이스 fetch(Data=full-tree, Process=process-flow, …).
   - `overlay_apply(live_copy, strategicDiff, tacticalDiff)` — 딥카피 위에 오버레이, temp id 부여, source 태깅.
2. **`services/overlay_apply.py`** — SemanticDiff ops(`obj_append`/`list_append`/CREATE)·StrategicDiff 를 라이브 dict 에 적용. `PREVIEW:<pid>:<idx>` 부여.
3. **`routes/proposals_preview.py`** — contracts/preview-api.md 의 엔드포인트. `resolve` + 뷰어별 미러. read 세션만.
4. **`router.py`** — preview 라우터 등록.
5. 게이트 테스트: preview 모듈에 `CREATE|MERGE|SET|DELETE` 없음 + 미리보기 전후 그래프 카운트 동일.

```bash
# 검증
curl -s "http://127.0.0.1:8000/api/proposals/PRO-001/preview/resolve?nodeId=AGG-refund&nodeLabel=Aggregate" | jq
curl -s "http://127.0.0.1:8000/api/proposals/PRO-001/preview/contexts/BC-payment/full-tree" | jq '.aggregates[].source'
```

---

## 프런트 구현 순서

1. **뷰어 스토어 4종에 preview-source 능력**(도메인 중립):
   - `aggregateViewer.store.js`, `canvas.store.js`, `bpmn.store.js`, `eventModeling.store.js`
   - `previewSource` ref + `setPreviewSource/clearPreviewSource` + fetch base 분기 + `readOnly` 시 mutation no-op.
2. **`proposals/proposalPreview.js`** — `openPreview(proposalId, target)` → `robo:open-preview` emit.
3. **`OpenInViewerLink.vue`** — nodeLabel→viewer 매핑, renderable=false 시 비활성 + 사유.
4. **UI 배선** — `ImpactMapView.vue`(행마다), `IntentDecompositionView.vue`(엔트리), `ProposalDetail.vue` 에 "열기" 링크.
5. **`App.vue`** — `robo:open-preview` 수신 → 탭 전환 + `setPreviewSource` + 포커스. `PreviewBanner.vue` 표시.

---

## 수동 검증 시나리오 (스펙 Acceptance 매핑)

| 시나리오 | 기대 | 스펙 |
|---------|------|------|
| 신규 Aggregate 항목 "열기" | Data 탭, 해당 Aggregate "신규" 배지 + 포커스 | US1-1 |
| 기존 Aggregate VO 추가 항목 "열기" | 라이브 Aggregate 위 새 VO "추가" 표시 | US1-2 |
| 변경 없는 impact 노드 "열기" | 라이브 모습 read-only 포커스 | US1-3 |
| 미리보기 중 화면 상단 | "PRO-NNN 미리보기 — 라이브 아님" 배너 | US1-4 / FR-007 |
| 미리보기 열고 닫은 후 라이브 Data 탭 | Aggregate 수·내용 동일, Neo4j 임시노드 0 | US2 / SC-003 |
| Process 변경 항목 "열기" | Process 탭, 프로세스 포커스 | US3-1 |
| 매핑 없는 항목 | "열기" 비활성 + 사유 | US3-3 / FR-010 |

---

## 라이브 오염 0 회귀 테스트 (US2, 필수)

```python
# api/features/proposal_lifecycle/tests/test_preview_projection.py
def test_preview_does_not_mutate_graph(neo4j):
    before = graph_checksum(neo4j)          # 노드/관계 카운트 + 속성 해시
    build_preview_for_target("PRO-001", "data", "AGG-refund")
    assert graph_checksum(neo4j) == before  # 단 하나도 변하지 않음
```

```ts
// frontend/tests/verify-proposal-preview-readonly.spec.ts
// 미리보기 열기→조작→닫기 후 라이브 Data 탭 Aggregate 목록 스냅샷 동일 확인
```

---

## 흔한 함정

- **mutation 액션 미차단**: preview `readOnly` 중 eventModeling 의 addNode/move* 가 라이브 엔드포인트로 새면 오염. no-op 가드 필수.
- **상태 누수**: 미리보기 진입 시 라이브 store 상태를 덮어쓰면 닫을 때 라이브가 깨짐 — 진입 전 스냅샷/별도 상태로 격리.
- **temp id 비결정성**: 인덱스가 아니라 무작위로 부여하면 반복 미리보기·포커스가 흔들림. 결정론 유지.
- **uvicorn --reload 누락**: 새 preview 라우트가 "not found" → Constitution IX 런북 확인.
