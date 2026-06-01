# Figma Plugin — Pending Improvements

작성일: 2026-06-01

이 세션에서 Figma 플러그인 ↔ Robo Architect 양방향 sync 작업을 하면서
정리된, **별도 PR로 다뤄야 할 잔여 작업**들. 우선순위 순서.

---

## 1. open-pencil FrameEditor 의 텍스트 박스 클리핑 (HIGH)

### 증상
Figma에서 만들어진 UI를 RA의 Inspector → Preview/Design 탭으로 가져오면
**텍스트가 박스 크기보다 길어서 잘려 보임.** Figma 에서는 정상 표시.

### 원인
open-pencil 의 CanvasKit 기반 렌더러가 사용하는 폰트 메트릭이 Figma 와
달라서, 같은 문자열을 그릴 때 글리프가 약간 더 넓어짐. TEXT 노드의
바운딩 박스는 Figma 의 값을 그대로 사용하므로 오버플로우가 발생.

### 시도한 임시 처리 (효과 없음)
[api/features/ingestion/figma_plugin_ws.py](../../api/features/ingestion/figma_plugin_ws.py)
의 `_figma_export_to_scene_graph` 에서:
- `textAutoResize = "WIDTH_AND_HEIGHT"` 강제 (유지)
- 모든 컨테이너의 `clipsContent = false` 강제 (유지)
- TEXT 노드 `width * 1.2` 패딩 (revert 함 — 효과 없었음)

### 진짜 해결책
오픈 펜슬 자체의 렌더러를 손봐야 함. 후보:
- `textAutoResize` 값을 실제로 존중해서 layout 후 box 를 재계산
- Figma 와 동일한 폰트 메트릭 (Inter 등) 을 CanvasKit 에 정확히 임베드
- TEXT 그릴 때 측정 후 box 를 측정 결과로 덮어쓰기

오픈 펜슬은 별도 OSS 라 robo-architect repo 안에서 직접 패치하기보다
upstream 에 PR 권장. submodule SHA 만 따라가도록.

---

## 2. FrameEditor 의 deserialize → edit → serialize 시각 desync (MEDIUM)

### 증상 (이미 우회 처리됨)
Save & Sync 후 패널 UI 가 깨지는 현상. EditorCanvas / PropertiesPanel
같은 자식 컴포넌트가 setup 시 inject 한 옛 editorStore 를 가리키고
있는데, `watch(props.sceneData)` 가 새 store 를 만들면 부모만 새 store
로 렌더 → 자식 stale → 시각 desync.

### 현재 우회 ([InspectorPanel.vue#onDesignSave](../../frontend/src/features/canvas/ui/InspectorPanel.vue))
저장 후 `designEditorKey++` 로 FrameEditor 전체 unmount/remount.
setup() 재실행, provideEditor() 새 store 로 갱신, 자식 inject() 깨끗하게
재구성. 동작은 정상이지만 매 저장마다 통째로 다시 그림 — flash 있음.

### 진짜 해결책
FrameEditor 의 `watch(props.sceneData)` 가 새 store 를 만들 때
provideEditor 도 같이 refresh 하도록 (현재는 setup 1회만). Vue 의
provide/inject 는 동적 refresh 가 불가능하므로 child 들이 `inject` 대신
reactive ref (`store.value`) 를 직접 사용하도록 리팩토링 필요.

---

## 3. 일부 UI 의 빈 sceneGraph (HIGH — 인제션 단계 품질)

### 증상
인제션 후 일부 UI (특히 Query/Validate/Check 류) 의 sceneGraph 가
DOCUMENT + CANVAS + 빈 FRAME 만 있고 TEXT/RECTANGLE 0 개. Design 탭에
열어도 빈 채로 보이고 Figma 에도 빈 frame 만 푸시됨.

해당 세션 (2026-06-01) 에서 28 개 UI 중 9 개가 이 상태였음:
- 자동납부 신청서 접수, 카드 발급사/매입사 식별
- 자동납부 신청변경 처리결과 반환, 입력값 검증
- 하나모바일 카드 적격성, 자동납부 신청 유효성 상태
- 자동납부 처리 결과, 하나모바일 카드 제한 여부
- 카드사 정보 식별 결과

### 원인
JSX 에이전트가 추상적 상태 UI (조회/검증 결과만 보여주는 화면) 에
대해 빈 frame 만 출력. command/form 류는 잘 만들지만 read-only 류엔
약함.

### 해결책
[api/features/ai_design/wireframe_agent.py](../../api/features/ai_design/wireframe_agent.py)
와 [api/features/ingestion/workflow/phases/ui_wireframes.py](../../api/features/ingestion/workflow/phases/ui_wireframes.py)
의 system prompt 에 다음 가이드 추가:
- Query/ReadModel/Validate 류 UI 도 상태 표시 카드/패널 + 결과 텍스트로
  최소 콘텐츠를 만들 것
- 빈 frame 출력 금지 — 최소 1 개 이상의 TEXT 노드 보장
- 적절한 placeholder 데이터 (e.g. "조회 결과 없음", "검증 통과") 포함

---

## 4. FramePreviewChat.vue 의존성 (LOW — upstream blocked)

### 증상
머지 시 vite 가 `Cannot find module 'open-pencil-fed/FramePreviewChat.vue'`
로 죽음.

### 원인
spec 034 의 WIP 커밋 `de030de` (`chore(034): WIP — desktop icons, Claude
IDE terminal/file panes, electron`) 이 [InspectorPanel.vue](../../frontend/src/features/canvas/ui/InspectorPanel.vue)
에 import 만 추가하고 open-pencil 서브모듈에 실제 파일을 커밋 안 함.

### 현재 우회
import 를 기존 `FramePreview.vue` 로 alias.

```js
const FramePreviewChat = defineAsyncComponent(
  () => import('open-pencil-fed/FramePreview.vue')
)
```

### 진짜 해결책
spec 034 작업자가 open-pencil 에 `FramePreviewChat.vue` 를 커밋 +
서브모듈 SHA 업데이트. 그 후 alias 제거.

---

## 5. 단일 워커 freeze 위험 (MEDIUM)

### 증상 (현재 dev.sh 의 `--timeout-graceful-shutdown 3` + trap SIGKILL 로 부분 우회)
full-sync 같은 long-running 백그라운드 태스크가 비-데몬 스레드
(httpx 동기 호출 등) 를 들고 있어 SIGTERM 에 응답 안 함. dev 환경에선
Ctrl+C 후 좀비 백엔드로 8000 포트 점유, `Address already in use` 로
다음 실행 실패.

### 현재 우회
dev.sh trap 이 1 초 grace 후 SIGKILL.

### 진짜 해결책
- `httpx.post` (동기) 를 `httpx.AsyncClient.post` 로 전부 교체
- 백그라운드 태스크에 cancellation token 추가, SIGTERM 시 cleanup
- 또는 long-running 작업은 별도 worker process (uvicorn + celery / arq)

---

## 6. 인스펙터 UI 자잘한 마무리 (LOW)

### 6.1 비활성 버튼 호버 시 hourglass 커서 → not-allowed (DONE)
[InspectorPanel.vue](../../frontend/src/features/canvas/ui/InspectorPanel.vue)
의 `.ui-preview-panel__btn:disabled` 에서 `cursor: wait` → `cursor: not-allowed`.

### 6.2 figma 모드에서 HTML template 없는 UI 의 'Copy wireframe code' 버튼 숨김 (DONE)
`v-if="node.data?.template"` 으로 조건부 렌더.

### 6.3 중복 아이콘 정리 (DONE)
Legacy `exportToFigma` (template → Figma clipboard) 와
`copySceneGraphToFigma` (sceneGraph → Figma clipboard) 가 같은 아이콘
사용. 전자 제거.

### 6.4 Floating sync 토스트 노출 위치 버그 (DONE)
v-if 컨테이너 안에 있어서 안 보이던 것 → 템플릿 루트 직하로 이동.

---

## 7. 자동 sync 폴링 제거 (DONE — 회귀 방지 필요)

기존에 Inspector Design 탭이 열려있는 동안 5 초마다
`/api/figma-plugin/get-result` 를 폴링해서 받은 sceneGraph 로 로컬을
덮어쓰던 legacy 경로 제거. **frame_name 기반 키 충돌로 다른 UI 의 빈
export 가 들어와서 로컬 풍부 데이터를 덮는 사고가 잦았음** — 사용자가
다음 Save 누르면 빈 데이터가 Neo4j 에 영속.

### 회귀 방지
- Figma → RA 는 명시적 "Figma에서 가져오기" 버튼 경유 (`/pull-frame/{ui_id}`)
- 폴링은 다시 추가하지 말 것. 필요하면 SSE / WebSocket 으로 push 모델.

---

## 작업 우선순위 정리

| # | 작업 | 우선순위 | 담당 영역 |
|---|---|---|---|
| 1 | 텍스트 박스 클리핑 | 🔴 HIGH | open-pencil submodule |
| 3 | 빈 sceneGraph (9 UI) | 🔴 HIGH | wireframe agent prompt |
| 2 | FrameEditor desync | 🟡 MEDIUM | open-pencil submodule |
| 5 | 워커 freeze 근본 픽스 | 🟡 MEDIUM | api 비동기화 |
| 4 | FramePreviewChat 미커밋 | 🟢 LOW | spec 034 작업자 |
| 6 | 인스펙터 UI 마무리 | 🟢 LOW | DONE |
| 7 | 자동 sync 회귀 방지 | 🟢 LOW | DONE |

이 세션에서 #6, #7 은 처리 완료. #1, #2, #3, #4, #5 는 별도 PR.
