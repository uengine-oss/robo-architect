# Implementation Plan: 056 — open-pencil upstream 동기화 + Proposal 초안 스토리보드

**Branch**: `056-open-pencil-upstream-sync` (base `044-design-import`)
**Spec**: [spec.md](spec.md) · **Status**: 구현 완료

---

## 기술 결정

| # | 결정 | 근거 |
|---|---|---|
| D1 | 서브모듈을 upstream master로 **재작성**(rebase 아님) | fork와 upstream 사이 1,491 커밋 + v0.14 패키지 분리로 3-way merge가 무의미. `robo-upstream-sync` 브랜치를 upstream master에서 새로 따고 커스텀만 다시 얹는다. 이전 상태는 `robo-fork-legacy`로 보존 |
| D2 | sceneGraph 전송 포맷 **유지** | Neo4j 저장분·Figma 플러그인·`wireframe_render.py`가 이 포맷을 읽는다. upstream의 `serializeSceneGraph`(배열 기반)는 내부용으로만 쓰고, 브리지는 기존 `{nodes, rootId, images}` 맵 포맷을 계속 만든다 |
| D3 | 누락 필드는 `createDefaultNode()`로 채움 | upstream SceneNode에 필드가 계속 늘어난다. 역직렬화 시 타입별 기본값으로 채우면 예전에 저장된 노드도 최신 렌더러에서 동작한다 |
| D4 | `instanceOverrides`는 upstream 직렬화 헬퍼 사용 | Map 2단 구조라 JSON.stringify가 `{}`로 뭉갠다. `serializeInstanceOverrideState`/`deserializeInstanceOverrideState`로 배열 형태로 왕복 |
| D5 | 네이티브 `<Instance>`는 **라이브러리 모드만** | 컴포넌트가 렌더 그래프 안에 있는 wireframe-service 경로에서만 유효하다. Figma 바인딩 모드(`figma-with-components`)는 컴포넌트가 Figma에 있으므로 마커+retype을 유지 |
| D6 | 마커 → Instance 변환은 **서비스 안에서** | 백엔드 프롬프트를 바꿔도 과거에 저장된 JSX·다른 호출자가 마커를 보낼 수 있다. 서비스가 입구에서 정규화하면 한 곳만 고치면 된다 |
| D7 | 스토리보드는 `Proposal` 속성 1개 | 신규 노드/관계 0건(Constitution I). 저니는 이미 `Proposal.journeys`에 있고, 스토리보드는 그 파생물이라 수명이 같다 |
| D8 | 렌더는 `run_render_agent` 재사용 | spec 024 lessons L3 — 손으로 만든 autolayout은 Figma 필드명을 섞어 쓰다 깨졌다. JSX → open-pencil Yoga 경로를 항상 거친다 |
| D9 | 진행 상태는 in-memory job + Neo4j 양쪽 | 새로고침해도 부분 결과가 보여야 한다. 화면 하나가 끝날 때마다 저장 |
| D10 | `ProposalResponse`에는 경량 스토리보드 | 화면 4개 sceneGraph가 수 MB다. 목록/상세 응답에는 `hasScene` 플래그만, 전체는 전용 엔드포인트로 |

---

## 아키텍처

```
Intent 스킬 완료
   │  _save_intent_result()  (strategicDiff + journeys 저장)
   ▼
schedule_storyboard(proposal_id, force=True)      ← 056 신규
   │
   ▼
storyboard_runner.run_storyboard()
   ├─ build_screen_plan(strategicDiff, journeys, prompt)
   │     journeys → [{id, name, steps:[{kind: screen|gateway, …}]}]
   │     저니 없으면 UserStory 순서로 합성 · 화면 12개로 예산 제한
   ├─ _catalog_context()  →  wireframe_agent.native_component_context()
   │     open-pencil 라이브러리 살아 있으면 <Instance> 지침 + 카탈로그
   └─ asyncio.gather(_render_step × N, Semaphore(2))
         run_render_agent(name, description, extra_context)
            └─ LLM → JSX → POST :7610/render → SerializedSceneGraph
         화면 하나 끝날 때마다 Neo4j 저장
   ▼
Proposal.storyboard (JSON)
   ▼
GET /api/proposals/{id}/storyboard?scenes=1
   ▼
ProposalStoryboard.vue  (Intent 탭 상단)
   ├─ FramePreview  (DOM 미리보기, CanvasKit 미사용)
   └─ ✎ → FrameEditor  (CanvasKit 편집기) → PUT …/steps/{id}
```

---

## 파일 배치

### open-pencil 서브모듈 (`robo-upstream-sync`)

| 파일 | 성격 |
|---|---|
| `src/federation/{FrameEditor,FullPageEditor,AIChat,FramePreview,FramePreviewChat}.vue` | 재작성 — upstream `createEditorStore`/`setActiveEditorStore`/`provideEditor` 기반 |
| `src/federation/bridge/serialize.ts` | 재작성 — `createDefaultNode` 보강 + `instanceOverrides` 왕복 |
| `src/federation/bridge/{html-to-scene,scene-to-html}.ts` | import 경로만 `@open-pencil/scene-graph`로 |
| `packages/cli/src/wireframe-service.ts` | 재작성 — 변형 카탈로그, 마커→Instance 정규화, 오버라이드 키 매핑 |
| `packages/core/src/design-jsx/renderer.ts` | 패치 — `variant={{…}}` 객체 지원, 아이콘 실패 시 플레이스홀더 |
| `packages/core/src/icons/index.ts` | 패치 — Iconify 응답에 `icons` 없을 때 방어 |
| `packages/core/src/canvas/renderer/colors.ts`, `color/okhcl.ts` | 패치 재적용 — `boundVariables`/`pluginData` 누락 허용 |

### robo-architect

| 파일 | 성격 |
|---|---|
| `api/features/proposal_lifecycle/services/storyboard_runner.py` | 신규 — 화면 계획·렌더·저장 |
| `api/features/proposal_lifecycle/routes/proposals_storyboard.py` | 신규 — 3개 엔드포인트 |
| `api/features/proposal_lifecycle/services/intent_runner.py` | 수정 — Intent 완료 시 스토리보드 예약 |
| `api/features/proposal_lifecycle/proposal_contracts.py` | 수정 — `storyboard` 필드(경량) |
| `api/features/figma_binding/component_library.py` | 수정 — `build_native_instance_context()` 추가, `native_instances=` 플래그 |
| `api/features/ai_design/wireframe_agent.py` | 수정 — `native_component_context()` 추출, Design 탭 생성에도 카탈로그 주입 |
| `frontend/src/features/proposals/ui/ProposalStoryboard.vue` | 신규 — 스토리보드 UI |
| `frontend/src/features/proposals/ui/ProposalDetail.vue` | 수정 — Intent 탭 상단에 삽입 |
| `frontend/src/features/proposals/proposals.store.js` | 수정 — fetch/generate/updateStep |
| `frontend/src/app/messages.js` | 수정 — ko/en 문자열 15개 |
| `frontend/vite.config.js` | 수정 — upstream alias 헬퍼·raw-md 플러그인·define·CanvasKit 정렬·`VITE_API_PROXY` |
| `frontend/src/features/aiDesign/fonts.js` | 수정 — `fontManager` API로 이행 |
| `scripts/seed_proposal_storyboard_demo.py` | 신규 — 데모 시드 |

---

## Constitution 게이트

| 원칙 | 판정 | 근거 |
|---|---|---|
| I. 그래프가 원천 | PASS | 신규 노드/관계 0건. `Proposal` 속성 1개만 추가 |
| II. 기존 뷰어 재사용 | PASS | FramePreview·FrameEditor를 그대로 임베드. 새 렌더러를 만들지 않음 |
| III. 진행은 스트리밍/폴링 | PASS | 화면 단위로 저장하고 UI가 2.5초 폴링. 부분 결과 즉시 노출 |
| IV. 제안→확인→적용 | PASS | 스토리보드는 읽기 전용 초안. 편집은 명시적 저장(PUT)에서만 반영 |
| V. 피처 간 결합 금지 | PASS | 스토리보드는 `ai_design.run_render_agent`만 호출(공개 함수). proposals ↔ figma_binding 직접 결합 없음 |
| VI. 실패 격리 | PASS | 화면별 try/except. 하나 실패해도 나머지 진행 |
| VII. 하위 호환 | PASS | sceneGraph 포맷 불변, 마커 JSX 계속 지원 |
| X. 스킬 우선 | N/A | 신규 스킬 없음 — 기존 Intent 스킬 결과를 소비만 함 |

---

## 리스크와 대응

| 리스크 | 대응 |
|---|---|
| upstream이 또 크게 바뀐다 | federation은 `@/app/editor/session`·`active-store` 두 진입점에만 의존하도록 좁혔다. 다음 동기화 때 확인할 지점이 명확 |
| 스토리보드 렌더 비용(LLM 호출 N회) | 화면 12개 예산 + 동시 2개 + Intent 완료 시 1회만 자동 실행. 재생성은 명시적 버튼 |
| 컴포넌트 라이브러리 부재 환경 | `is_available()` 확인 후 카탈로그 없이 프리미티브로 렌더 |
| CanvasKit 버전 불일치 | vite가 open-pencil의 `canvaskit-wasm`을 alias + `public/canvaskit.wasm`을 매 빌드 덮어씀 |
