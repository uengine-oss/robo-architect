# Implementation Plan: Proposal Impact Artifact Preview

**Branch**: `040-proposal-impact-preview` | **Date**: 2026-06-11 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/040-proposal-impact-preview/spec.md`

---

## Summary

Proposal 의 Impact / Diff 항목마다 **"열기" 진입점**을 달아, 항목 타입에 맞는 기존 뷰어(**Data** `AggregatePanel` · **Design** `CanvasWorkspace` · **Process** `BpmnPanel` · **Processes** `EventModelingPanel`)를 **읽기 전용 미리보기 모드**로 열어 해당 노드를 포커스한다.

핵심 기술 결정(스펙 Clarification 확정): 복제 Neo4j 를 만들지 않고, **오버레이 투영(Overlay Projection)** 을 채택한다. 미리보기 요청 시 백엔드가 **(라이브 그래프의 관련 슬라이스) + (Proposal 의 직렬화된 strategicDiff/tacticalDiff 오버레이)** 를 합성해, **기존 라이브 read 엔드포인트와 동일한 응답 형태**로 반환하는 `preview` 프리픽스 엔드포인트를 제공한다. 프런트엔드 뷰어 스토어는 "preview source 주입" 한 가지만 추가하면 기존 렌더링/포커스 로직을 그대로 재사용한다. 미리보기는 어떤 경우에도 라이브 그래프에 기록하지 않는다(Constitution I).

신규 AI 워크플로 없음 — diff 는 이미 039 인텐트 분해가 생산한다. 본 기능은 순수 read/projection/render 이므로 새 Skill 불필요(Principle X N/A).

---

## Technical Context

**Language/Version**: Python 3.11+ (백엔드), Vue 3 + Vite (프런트엔드)

**Primary Dependencies**: FastAPI, Neo4j(공식 드라이버), Pydantic, Vue Flow, bpmn-js, Pinia. SSE 불필요(투영 합성은 즉시 그래프 질의).

**Storage**: Neo4j 4.4+ — 읽기 전용. 신규 노드 라벨/제약 없음. 미리보기 데이터의 원천은 기존 `Proposal.strategicDiff/tacticalDiff/impactMap`(039) 직렬화 속성. 별도 영속 저장소·복제 DB 없음.

**Testing**: pytest(백엔드 투영 합성·오염 0 검증), Playwright(프런트 E2E — 열기→포커스→배너→라이브 무변경)

**Target Platform**: Linux/macOS 서버 + 웹 브라우저

**Project Type**: Full-stack 웹 애플리케이션 (Feature-modular). 039 proposal_lifecycle 피처 확장 + 기존 viewer 스토어에 generic preview-source 주입.

**Performance Goals**: "열기" → 뷰어 포커스까지 **2s 이내**(SC-004). 투영 합성은 단일 BC 슬라이스 + JSON 오버레이이므로 instant query 범주.

**Constraints**: 라이브 그래프 무변경(Constitution I, US2) — 투영은 read 트랜잭션만. Viewer 스토어는 proposals 피처를 직접 임포트하지 않는다(Constitution V) — generic preview-source + 앱 레벨 이벤트로 구동.

**Scale/Scope**: 임팩트 수십 항목 / 제안. 4개 뷰어. 동시 다중 제안 미리보기 격리(US2-3).

---

## Constitution Check

*GATE: Phase 0 전 통과 필수. Phase 1 설계 후 재검토.*

| 원칙 | 검토 결과 |
|------|----------|
| **I. Graph-as-Source-of-Truth (NON-NEGOTIABLE)** | ✅ PASS — 미리보기는 **읽기 전용 파생 투영**. 라이브 그래프에 절대 쓰지 않음(복제 DB·임시쓰기 모두 배제). 투영은 언제든 재생성 가능한 projection. US2 + FR-006/012 가 이를 강제. |
| **II. Event Storming Vocabulary** | ✅ PASS — Aggregate/Command/Event/UserStory/BoundedContext/Process 용어 유지. 노드 라벨·경로 동일. |
| **III. Streaming-First UX** | ✅ PASS — 투영 합성은 "instant graph query"(단일 슬라이스+오버레이, <2s)이므로 request/response 허용(원칙 III 예외 조항). 신규 장기 작업 없음. |
| **IV. Human-in-the-Loop on Mutations** | ✅ PASS (vacuously) — 본 기능은 **mutation 자체가 없음**. 제안 적용은 039 Dual Merge 의 책임이며 본 기능 범위 밖. |
| **V. Feature-Modular** | ✅ PASS — 백엔드는 `api/features/proposal_lifecycle/`(preview routes + projection service). 프런트는 viewer 스토어에 **generic preview-source 주입 능력**만 추가(proposals 임포트 금지), proposals 피처가 **앱 레벨 이벤트**(`robo:open-preview`, 기존 `robo:switch-tab`/`claude-terminal-open` 패턴)로 구동. 교차 의존은 이벤트/플랫폼 경유. |
| **VI. Provider-Agnostic LLM** | ✅ N/A — LLM 호출 없음. |
| **VII. Observable by Default** | ✅ PASS — preview 엔드포인트에 correlation ID + 단계 로그(`preview_projection_start/built`). |
| **VIII. Figma SceneGraph Pipeline** | ✅ N/A — SceneGraph 생성 없음. |
| **IX. Plugin ↔ Backend Dev-Loop** | ✅ N/A — Figma 플러그인 무관. |
| **X. Skill-First Deep Agent (NON-NEGOTIABLE)** | ✅ N/A — **신규 AI 워크플로 없음**. diff 는 039 `robo-proposal-intent` 가 이미 생산. 본 기능은 결정론적 read/projection 이라 Skill 불필요. |

**초기 Constitution PASS — 위반 없음. Complexity Tracking 불필요.**

### 모듈 경계 주의 (Principle V)

뷰어 스토어(`canvas`, `eventModeling` 피처 소유)는 proposals 를 *알지 못한다*. 추가하는 것은 도메인 중립적 능력뿐:

```
viewer store.setPreviewSource({ baseUrl, label, readOnly:true }) / clearPreviewSource()
```

proposals 피처는 이 능력을 **직접 임포트가 아니라** 앱 레벨 이벤트로 구동한다 — `App.vue` 가 `robo:open-preview` 를 수신해 탭 전환 + 대상 스토어의 `setPreviewSource` + 포커스를 오케스트레이션. 이로써 sibling-feature 직접 임포트(금지)를 피한다.

---

## Project Structure

### Documentation (this feature)

```text
specs/040-proposal-impact-preview/
├── plan.md              # 이 파일
├── research.md          # Phase 0 ✅
├── data-model.md        # Phase 1 ✅
├── quickstart.md        # Phase 1 ✅
├── contracts/
│   └── preview-api.md   # Phase 1 ✅ (preview read 엔드포인트 계약)
├── checklists/
│   └── requirements.md  # /speckit-specify 산출
└── tasks.md             # /speckit-tasks 출력 (미생성)
```

### Source Code (repository root)

```text
# Backend (Python / FastAPI) — 039 피처 확장
api/features/proposal_lifecycle/
├── routes/
│   ├── proposals_preview.py        # 신규: preview read 엔드포인트 (live shape mirror, read-only)
│   └── proposals_preview_edit.py   # 신규(US4): 편집 → 제안 diff (PUT preview/aggregate, POST preview/chat-confirm)
├── services/
│   ├── preview_projection.py       # 신규: 오버레이 투영 합성 엔진 (핵심)
│   ├── overlay_apply.py            # 신규: SemanticDiff/deep ops → live 슬라이스에 오버레이
│   └── preview_edit.py             # 신규(US4): 편집 reconcile → Proposal.tacticalDiff (라이브 무변경)
└── router.py                       # preview / preview_edit 라우터 등록 추가

api/platform/
└── neo4j_helpers.py                # (기존) load_domain_nodes 재사용 + BC 슬라이스 read helper 추가 고려

# Frontend (Vue 3)
frontend/src/features/proposals/ui/
├── ProposalDetail.vue              # 수정: 임팩트/diff 항목에 "열기" 링크 배선
├── ImpactMapView.vue               # 수정: 행마다 "열기" 버튼 (viewer 라우팅)
├── IntentDecompositionView.vue     # 수정: strategic/tactical 엔트리에 "열기"
├── ProposalDiffVisualView.vue      # 수정(선택): 노드 클릭 → 열기
└── OpenInViewerLink.vue            # 신규: 공용 "열기" 링크 (타입→뷰어 매핑 + 비활성/사유)

frontend/src/features/proposals/
└── proposalPreview.js              # 신규: openPreview(proposalId, target) → robo:open-preview 이벤트 emit

frontend/src/features/canvas/
├── aggregateViewer.store.js        # 수정: setPreviewSource/clearPreviewSource + fetch base 분기
├── canvas.store.js                 # 수정: 동일 preview-source 능력
└── bpmn.store.js                   # 수정: 동일

frontend/src/features/eventModeling/
└── eventModeling.store.js          # 수정: 동일

frontend/src/app/ (또는 App.vue)
├── App.vue                         # 수정: robo:open-preview 수신 → 탭 전환 + setPreviewSource + 포커스
└── ui/PreviewBanner.vue            # 신규: "PRO-NNN 미리보기 — 라이브 아님" 식별 배너 (FR-007)

# Tests
frontend/tests/
├── verify-proposal-preview-aggregate.spec.ts   # Data 오버레이 미리보기
├── verify-proposal-preview-readonly.spec.ts     # 라이브 오염 0 (US2)
└── verify-proposal-preview-routing.spec.ts      # 4 뷰어 라우팅 + 비활성 사유
api/features/proposal_lifecycle/tests/
└── test_preview_projection.py                   # 오버레이 합성·temp id·라이브 무변경
```

**Structure Decision**: 039 proposal_lifecycle 피처를 확장(preview routes/services 추가)하고, 4개 viewer 스토어에는 **도메인 중립 preview-source 주입 능력**만 더한다. 신규 노드 라벨/스키마/스킬 없음. 핵심 신규 로직은 백엔드 `preview_projection.py`(오버레이 합성)와 프런트 `proposalPreview.js`(이벤트 오케스트레이션)에 격리된다.

---

## Phase 0: 연구 완료 ✅

[research.md](research.md) 참조. 주요 결정:

- **오버레이 투영 vs 복제 Neo4j vs 라이브 임시쓰기** → 오버레이 투영 채택(스펙 확정). 근거·기각 사유 정리.
- **응답 형태 미러링** → preview 엔드포인트는 라이브 read 엔드포인트의 응답 스키마를 그대로 반환 → 뷰어 스토어 파싱 무수정.
- **프런트 주입 방식** → generic `setPreviewSource` + 앱 레벨 `robo:open-preview` 이벤트(기존 `robo:switch-tab`/`claude-terminal-open` 패턴 재사용), Principle V 준수.
- **임시 노드 ID** → `CREATE`(id=null)에 `PREVIEW:<pid>:<seq>` 결정론적 임시 ID 부여 → 제안 내 신규 노드 상호 참조·포커스 해소.
- **타입별 깊이** → Data/Process 는 오버레이 합성, Design/Processes 는 대개 라이브 read-only 포커스(가용 시 오버레이).

---

## Phase 1: 설계 완료 ✅

| 아티팩트 | 파일 |
|---------|------|
| 데이터 모델 | [data-model.md](data-model.md) |
| API 계약 | [contracts/preview-api.md](contracts/preview-api.md) |
| 개발 퀵스타트 | [quickstart.md](quickstart.md) |

---

## 구현 가이드라인

### 오버레이 투영 합성 (preview_projection.py)

```python
async def build_preview_for_target(proposal_id: str, viewer: str, target_node_id: str) -> dict:
    # 1. Proposal 의 직렬화 diff 로드 (039 from_neo4j 재사용)
    p = load_proposal(proposal_id)            # strategicDiff, tacticalDiff
    # 2. 라이브 그래프 슬라이스 READ (트랜잭션, 쓰기 금지)
    live = read_live_slice(viewer, target_node_id)   # 예: BC full-tree, process-flow
    # 3. 오버레이 적용 (라이브 복사본 위에)
    projected = overlay_apply(live, p.strategicDiff, p.tacticalDiff)  # 메모리 only
    # 4. 라이브 엔드포인트와 동일한 응답 형태로 반환 + per-node source 태깅
    return tag_sources(projected)             # live | live+modified | temporary
```

- `read_live_slice` 는 **read 트랜잭션만** (Constitution I). 어떤 경로도 CREATE/MERGE/SET 금지.
- `overlay_apply` 는 라이브 dict 의 **딥카피** 위에서만 동작 — 원본 그래프 객체 변형 금지.
- 라이브에 없는 `MODIFY` 대상은 충돌 플래그(`source:'conflict'`)로 표기(엣지 케이스), 예외로 깨지지 않음.

### 임시 노드 ID 부여 (overlay_apply.py)

- `changeType=CREATE` 이고 `nodeId=null` 인 tactical/strategic 항목에 `PREVIEW:<pid>:<idx>` 결정론적 ID.
- 같은 제안 내 다른 신규 노드를 제목으로 참조하면 동일 temp ID 로 연결 → 프런트 포커스/엣지 해소.

### 프런트 preview-source 주입 (Constitution V 준수)

```js
// canvas/aggregateViewer.store.js (도메인 중립)
const previewSource = ref(null)  // { baseUrl, proposalId, label, readOnly }
function setPreviewSource(src) { previewSource.value = src }
function clearPreviewSource() { previewSource.value = null }
// fetch 분기: previewSource ? `${previewSource.baseUrl}/contexts/${bcId}/full-tree` : `/api/contexts/${bcId}/full-tree`
```

```js
// proposals/proposalPreview.js (proposals 피처)
export function openPreview(proposalId, target) {
  window.dispatchEvent(new CustomEvent('robo:open-preview', { detail: { proposalId, ...target } }))
}
// App.vue 가 수신 → activeTab 전환 → 대상 store.setPreviewSource(...) → store.focusX(targetId)
```

- 뷰어 스토어는 `proposals` 를 임포트하지 않는다. 오케스트레이션은 App.vue(앱 셸).
- `readOnly:true` 동안 스토어의 mutation 액션(addNode/deleteNode/createRelation 등)은 **no-op + 경고**(US2 안전).

### 식별 배너 (FR-007)

- preview-source 활성 시 해당 탭 상단에 `PreviewBanner` 표시: "🔍 PRO-NNN 미리보기 — 임시 데이터, 라이브 설계 아님 · [닫기]". 닫기 → `clearPreviewSource` + 라이브 재적재.

### 안전 수칙 (US2 / Constitution I)

- preview 엔드포인트는 Neo4j **read 트랜잭션 전용** 세션 사용. 코드 리뷰 게이트: preview 경로에서 CREATE/MERGE/SET/DELETE 문자열 금지(테스트로 강제).
- preview 와 라이브는 서로 다른 store 상태 키를 공유하지 않도록, preview 진입 시 라이브 상태 스냅샷 후 복원하거나 별도 미리보기 인스턴스 상태로 격리(다중 제안 격리 US2-3).

---

## Complexity Tracking

> Constitution Check 위반 없음 — 비움.

복제 Neo4j(기각)는 동기화·정리·인프라 복잡도를 더했을 것이고, 라이브 임시쓰기(기각)는 동시성/크래시 시 오염 위험을 더했을 것이다. 오버레이 투영은 추가 영속 상태 0, 신규 스키마 0 으로 최소 복잡도를 유지한다.
