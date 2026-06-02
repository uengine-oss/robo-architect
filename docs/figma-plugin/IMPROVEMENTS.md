# Figma Plugin — Pending Improvements

작성일: 2026-06-01

이 세션에서 Figma 플러그인 ↔ Robo Architect 양방향 sync 작업을 하면서
정리된, **별도 PR로 다뤄야 할 잔여 작업**들. 우선순위 순서.

---

## 1. open-pencil FrameEditor 의 텍스트 박스 클리핑 (HIGH) — ✅ FIXED 2026-06-02

### 증상
Figma에서 만들어진 UI를 RA의 Inspector → Preview/Design 탭으로 가져오면
**텍스트가 박스 크기보다 길어서 잘려 보임.** Figma 에서는 정상 표시.

### 진짜 원인 (찾음)
폰트 메트릭 차이는 부차적 요인이고, 핵심은 렌더러의 **하드 클립**이었음.
[open-pencil/packages/core/src/canvas/scene.ts](../../open-pencil/packages/core/src/canvas/scene.ts)
의 `renderText()` 가 `textAutoResize` 값과 무관하게 **항상**
`clipRect(0, 0, node.width, node.height)` 로 잘랐음.

`buildParagraph()` 는 `WIDTH_AND_HEIGHT` 일 때 longest line 으로 문단을
재레이아웃해서 폭을 키우는데(`canvas/text.ts:241-243`), 정작 그리는
시점의 클립이 Figma 가 준 (더 좁은) 박스로 다시 잘라버려서 오버플로우가
시각적으로 잘려 보였던 것.

### 적용한 수정
1. `renderText()` 클립이 `textAutoResize` 를 존중:
   - `WIDTH_AND_HEIGHT` → 두 축 모두 클립 안 함
   - `HEIGHT` → 폭만 클립, 높이는 무제한
   - `NONE` / `TRUNCATE` → 기존대로 박스 클립 (TRUNCATE 는 ellipsis 처리)
2. `buildTextPicture()` 의 recording cull rect 도 node 박스가 아니라
   실제 레이아웃된 문단 크기(`getLongestLine()` / `getHeight()`)로 잡아
   캐시된 picture 경로에서도 같은 잘림이 재발하지 않게 함.

ingestion 쪽 우회(`textAutoResize = "WIDTH_AND_HEIGHT"` 강제,
`clipsContent = false`)는 유지 — 이제 렌더러가 그 의도를 실제로 존중함.

### 잔여 (있다면)
폰트 메트릭을 Figma 와 100% 일치시키려면 여전히 Inter 등 동일 폰트를
CanvasKit 에 임베드하는 작업이 남지만, 잘림 증상 자체는 위 수정으로 해소.
open-pencil 은 별도 submodule 이므로 upstream PR 로 올리고 SHA 추적 권장.

---

## 2. FrameEditor 의 deserialize → edit → serialize 시각 desync (MEDIUM) — ✅ FIXED 2026-06-02

### 증상 (이미 우회 처리됨)
Save & Sync 후 패널 UI 가 깨지는 현상. EditorCanvas / PropertiesPanel
같은 자식 컴포넌트가 setup 시 inject 한 옛 editorStore 를 가리키고
있는데, `watch(props.sceneData)` 가 새 store 를 만들면 부모만 새 store
로 렌더 → 자식 stale → 시각 desync.

### 현재 우회 ([InspectorPanel.vue#onDesignSave](../../frontend/src/features/canvas/ui/InspectorPanel.vue))
저장 후 `designEditorKey++` 로 FrameEditor 전체 unmount/remount.
setup() 재실행, provideEditor() 새 store 로 갱신, 자식 inject() 깨끗하게
재구성. 동작은 정상이지만 매 저장마다 통째로 다시 그림 — flash 있음.

### 적용한 수정 (2026-06-02)
provide/inject 는 동적 refresh 가 안 되지만, **provide 하는 값 자체를 stable
proxy 로** 만들면 됨 — 이미 `stores/editor.ts` 의 전역 `storeProxy`(→
`useEditorStore()`)가 쓰는 패턴.

- [FrameEditor.vue](../../open-pencil/src/federation/FrameEditor.vue):
  `provideEditor(editorStore)` → `provideEditor(editorProxy)` 로 변경.
  `editorProxy` 는 매 접근마다 현재 `store.value` 로 forward 하는 Proxy.
  `watch(sceneData)` 가 `store.value = newStore` 로 갈아끼우면 `useEditor()`
  소비자(Toolbar/PropertiesPanel/headless canvas·text 프리미티브)가 **자동으로
  새 store 를 봄**. `hasSelection` 도 `editorStore` 직접참조 → `store.value`
  로 교체. watch 끝에 `newStore.requestRepaint()` 로 즉시 1회 리페인트.
- [InspectorPanel.vue#onDesignSave](../../frontend/src/features/canvas/ui/InspectorPanel.vue):
  저장 후 `designEditorKey++` (전체 remount = flash) **제거**. 이제 store
  교체가 in-place 로 반영되므로 unmount/remount 불필요. (탭 전환·pull 시의
  designEditorKey 사용은 그대로 둠 — 그건 다른 시나리오.)

### 후속 수정 (2026-06-02, 1차 테스트 회귀 대응)
1차 적용 후 테스트: Figma 동기화는 정상이나 패널이 (a) "수정 전" 으로
보이고 (b) zoom 이 매번 초기화되며 (c) 탭 왕복해야 수정본이 보임. 원인:
**watch 경로가 setup 보다 불완전**했음 — setup 은 `fixOrphanedFrames` +
`computeAllLayouts` 를 돌리는데 watch 는 deserialize+createStore 만 해서
auto-layout 없이 깨져 보였고, 새 store 라 zoom 도 기본값으로 리셋됨.
탭 전환은 remount→setup 전체 파이프라인을 돌려서 정상이었던 것.

- 공통 `buildStore(sceneData)` 헬퍼 추출 → setup 과 watch 가 **동일
  파이프라인**(deserialize+fixOrphanedFrames+computeAllLayouts) 사용.
- watch 에서 새 store 에 이전 store 의 `zoom/panX/panY` 를 **복사** →
  저장 round-trip echo 가 뷰포트를 안 흔듦.

### 2차 후속 (2026-06-02, 진짜 root cause — 렌더러 캐시)
2차 후 테스트: zoom 은 유지되나 **저장 후 여전히 "수정 전" 으로 보이고,
텍스트박스 이동 등 아무 렌더 액션을 주면 그제서야 수정본으로 바뀜.** →
데이터는 맞고(액션 주면 나옴) **캐시/렌더 문제**.

원인: 캔버스 렌더러(`SkiaRenderer`)가 scene picture 를 **`sceneVersion`
으로 캐싱**함 (renderer.ts: `sceneVersion === scenePictureVersion &&
pageId === scenePicturePageId` 이면 캐시 picture 재사용). 그런데:
- `requestRepaint()` 는 `renderVersion` 만 올리고 `sceneVersion` 은 안 올림.
- watch 가 만든 새 store 는 `createDefaultEditorState` 로 `sceneVersion=0,
  renderVersion=0` 부터 시작 → 렌더러에 캐시된 옛 `scenePictureVersion` 과
  **충돌 → 캐시 히트 → 옛 picture 그대로 그림(stale).**
- 텍스트박스 이동 등 그래프 변경이 `sceneVersion` 을 올려야 캐시 미스 →
  그제서야 새 내용. (증상과 정확히 일치.)

수정: watch 에서 새 store 의 버전 카운터를 **이전 store 에서 이어받아 +1**
(`newStore.state.sceneVersion = prev.state.sceneVersion + 1`, renderVersion
동일). 새 store 를 0 부터 시작시키지 않고 단조 증가시켜 렌더러가 "더 새
프레임" 으로 인식 → 캐시 무효화 → 저장 내용 **즉시** 렌더.

⚠️ 런타임 재검증 필요: Design 탭 → 편집 → Save & Sync 후 flash 없이,
zoom 유지된 채, **탭 전환/노드 이동 없이도** 수정본이 즉시 보이는지.

---

## 3. 일부 UI 의 빈 sceneGraph (HIGH — 인제션 단계 품질) — ✅ FIXED 2026-06-02

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

### 적용한 수정 (2026-06-02)
프롬프트만으로는 부족해서 **프롬프트 + 콘텐츠 게이트** 양쪽을 손봄.

1. **프롬프트** — [wireframe_agent.py](../../api/features/ai_design/wireframe_agent.py)
   `SYSTEM_PROMPT` 에 read-only/status/result 화면 섹션 추가:
   - 조회/검증/식별/유효성/결과/상태 류는 상태 카드 + `label: value` 결과 행 +
     상태 칩으로 실제 콘텐츠를 만들 것
   - **빈 frame 절대 금지 — 최소 1개 이상의 `<Text>` 보장**
   - placeholder 데이터 (e.g. "조회 결과 없음", "검증 통과", "적격") 포함
2. **콘텐츠 게이트** — 진짜 원인은 프롬프트가 아니라 **검증 부재**였음.
   render 가 DOCUMENT+CANVAS+빈 FRAME (truthy!) 를 돌려줘도 `if sg:` 를
   통과해 그대로 저장됐음. 이제:
   - `scene_graph_text_node_count()` / `scene_graph_has_visible_content()`
     헬퍼 추가 (TEXT 노드 0개 = 빈 frame 판정)
   - `run_render_agent` 루프: 렌더 성공해도 Text 0개면 LLM 에게
     "빈 frame 이다, 콘텐츠 넣어 다시 render" 라고 ToolMessage 로 피드백 →
     같은 루프 안에서 재시도. 비어있지 않은 결과를 우선 채택, 끝까지 비면
     best-effort 로 반환 (SSE 인터랙티브 경로용).
   - [ui_wireframes.py](../../api/features/ingestion/workflow/phases/ui_wireframes.py)
     `_generate_jsx_scene_graph_for_figma_mode`: `if sg:` →
     `if sg and scene_graph_has_visible_content(sg):` 로 변경. 빈 frame 이면
     fresh 에이전트로 재시도(최대 3회), 끝까지 비면 **None 반환** → UI 노드는
     sceneGraph 없이 생성(재생성 가능)되고 빈 frame 이 Figma 로 푸시되지 않음.

   figma-with-components 경로는 `retype_instance_markers` 로 TEXT 마커를
   INSTANCE 노드로 바꾸므로 TEXT-only 게이트를 적용하지 않음 (오탐 방지).

---

## 4. FramePreviewChat.vue 의존성 (LOW) — ✅ FIXED 2026-06-02

### 증상
머지 시 vite 가 `Cannot find module 'open-pencil-fed/FramePreviewChat.vue'`
로 죽음.

### 원인
spec 034 의 WIP 커밋 `de030de` (`chore(034): WIP — desktop icons, Claude
IDE terminal/file panes, electron`) 이 [InspectorPanel.vue](../../frontend/src/features/canvas/ui/InspectorPanel.vue)
에 import 만 추가하고 open-pencil 서브모듈에 실제 파일을 커밋 안 함.

### 적용한 수정 (2026-06-02)
누락 파일을 **실제로 생성**해 import 경로를 정직하게 만듦(alias 제거):
- [open-pencil/src/federation/FramePreviewChat.vue](../../open-pencil/src/federation/FramePreviewChat.vue)
  신규 — spec 034 의 chat/Claude-IDE 변형이 아직 없으므로, 같은 props 로
  read-only `FramePreview` 에 위임하는 **placeholder**. 호스트가 바인딩하는
  `save` emit 도 명시적으로 선언(spec 034 chat→edit 흐름용 예약).
- [InspectorPanel.vue](../../frontend/src/features/canvas/ui/InspectorPanel.vue):
  `import('open-pencil-fed/FramePreview.vue')` alias → 실제
  `FramePreviewChat.vue` import 로 교체.

spec 034 의 진짜 chat 변형이 upstream 에 오면 이 파일 본문만 교체하면 됨
(import 경로는 그대로). vue-tsc 신규 에러 0.

---

## 5. 단일 워커 freeze 위험 (MEDIUM) — ✅ FIXED 2026-06-02 (핫패스)

### 증상 (현재 dev.sh 의 `--timeout-graceful-shutdown 3` + trap SIGKILL 로 부분 우회)
long-running 백그라운드 태스크(bulk 인제션 등)가 비-데몬 스레드
(`asyncio.to_thread(동기 httpx)`, `to_thread(llm.invoke)`) 를 들고 있어
SIGTERM 에 응답 안 함. 동기 httpx.post(timeout=120) 가 worker 스레드 안에
갇히면 cancel 불가 → 인터프리터 종료가 요청 타임아웃까지 블록. dev 에선
Ctrl+C 후 좀비 백엔드로 8000 포트 점유.

### 적용한 수정 (2026-06-02)
핵심 블로킹 스레드 2종을 **async (cancellable) 로 전환** — 이벤트 루프가
종료 시 in-flight 요청을 깔끔히 취소함:
1. **wireframe 렌더 httpx** — [open_pencil_client.py](../../api/platform/open_pencil_client.py)
   에 `render_wireframe_async` / `is_available_async` /
   `parse_and_render_llm_output_async` (httpx.AsyncClient) 추가. bulk
   경로([wireframe_agent.py](../../api/features/ai_design/wireframe_agent.py)
   `_render_jsx`, [ui_wireframes.py](../../api/features/ingestion/workflow/phases/ui_wireframes.py))
   가 `to_thread(동기 httpx)` → `await ..._async()` 로 전환. (동기 함수는
   라우트/ddd_spec 호환 위해 유지.)
2. **LLM invoke** — `invoke_sync_llm_with_backoff` 가 `to_thread(llm.invoke)`
   대신 모델의 네이티브 `ainvoke` 사용(없으면 to_thread fallback). figma
   JSX 에이전트는 이미 `ainvoke` 사용 중.

이로써 bulk 인제션의 await 들이 cancellable → SSE 끊김/shutdown 시
CancelledError 가 자연 전파(별도 cancellation token 불필요). full-sync 는
이미 async + 명시적 cancel 보유.

### 잔여
- `figma_sync.py` 의 pull 경로 동기 render import (request-scoped, 직접 빌드
  위주라 freeze 영향 작음) 는 그대로 둠.
- dev.sh 의 SIGKILL trap 은 **안전망으로 유지** (다른 sync to_thread —
  Neo4j 드라이버 등 — 가 드물게 남을 수 있음).
- 완전 분리가 필요하면 별도 worker process(arq/celery) 는 여전히 후보.

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

## 8. bulk 생성 중 LLM 429 (rate limit) — ✅ FIXED 2026-06-02

### 증상
인제션 와이어프레임 bulk 생성 도중 LLM API 가 `429 Too Many Requests`.

### 원인
[ui_wireframes.py](../../api/features/ingestion/workflow/phases/ui_wireframes.py)
가 UI 를 `BATCH_SIZE = 10` 으로 동시 생성하고, 각 UI 의
`run_render_agent` 가 멀티스텝(스텝마다 LLM 호출)이라 한순간에 수십 개의
LLM 요청이 in-flight → provider rate limit 초과. 기존엔 LLM 예외가
나면 `return None, None` 로 그 UI 를 버리고, 인제션이 fresh 에이전트로
재시도 → 429 가 캐스케이드. (#3 의 빈-frame nudge 가 호출 수를 더 늘려
악화시킴.)

### 적용한 수정
[wireframe_agent.py](../../api/features/ai_design/wireframe_agent.py) 에:
- **프로세스 전역 LLM 동시성 세마포어** (`_LLM_SEM`, 기본 4,
  `WIREFRAME_LLM_CONCURRENCY` 로 조정). 배치가 10-wide 여도 동시 LLM
  호출은 4 개로 큐잉됨. user_stories.py 의 `MAX_CONCURRENT_CHUNKS=3`
  ("429 위험 최소화") 정책과 동일 선상.
- **429 backoff 재시도** (`_with_llm_backoff`): 429 감지 시
  `Retry-After` 헤더 존중, 없으면 지수 백오프(최대 30s, 5회). 429 가
  아닌 에러·타임아웃은 즉시 전파.
- figma JSX 에이전트(`_ainvoke_with_backoff`) 와 HTML/component-JSON 경로
  (`invoke_sync_llm_with_backoff`) 가 **같은 세마포어를 공유** → 모드
  무관하게 단일 rate-limit 예산.

세마포어는 in-flight 만 제한하므로 BATCH_SIZE 는 그대로 둠(처리량 유지).

### 추가: LLM 호출 무한 hang 방지 (2026-06-02)
figma JSX 에이전트의 `bound.ainvoke` 에 **타임아웃이 없었음** — HTML/component
경로는 `wait_for(300s)` 가 있었는데 figma-mode 만 빠져 있었음. "모델 승격"
(엔드포인트 교체) 후 새 provider 가 응답 없이 연결만 잡고 있으면 그 호출이
무한 대기 → 인제션 배치 전체가 0% CPU 로 정지(겉보기엔 "동기화 중 멈춤").
`_ainvoke_with_backoff` 를 `asyncio.wait_for` 로 감쌈(기본 300s,
`WIREFRAME_LLM_TIMEOUT_SEC` 로 조정). 타임아웃은 429 가 아니므로 즉시 전파 →
해당 UI 만 실패하고 런은 계속됨. (이 hang 은 render 500 과 무관 — render 는
httpx 120s 타임아웃이 이미 있었고 산발적 500 은 재시도로 흡수됨.)

---

## 9. 플러그인 "연결됨" ↔ RA 바인딩 desync (MEDIUM) — ✅ FIXED 2026-06-02

### 증상
Figma 플러그인은 "연결됨" 으로 표시되는데 RA 쪽 `GET /api/figma-binding`
은 404 (바인딩 없음). 플러그인을 **통째로 껐다 켜서** 연결 해제→재연결
하면 복구됨. (단순 "연결 해제 → 연결" 만으론 복구 안 됨.)

### 원인
플러그인의 "연결됨" 은 `/api/figma-plugin/status` 헬스 핑 200 일 뿐,
RA 가 파일을 등록/바인딩했는지와 무관. RA 가 필요로 하는 두 가지의
자가복구 여부가 다름:

| RA 필요 항목 | 등록 방식 | 백엔드 재시작/그래프 wipe 후 |
|---|---|---|
| 플러그인 메타데이터 (`_plugin_metadata`) | 매 3초 poll 마다 lazy 재등록 ([figma_plugin_ws.py](../../api/features/ingestion/figma_plugin_ws.py) `/poll`) | ✅ 자동 복구 |
| 바인딩 레코드 (`FigmaBinding`) | `POST /connect` 1회, `bindingRegistered` 플래그 가드 | ❌ 복구 안 됨 |

[figma-plugin/src/ui.html](../../figma-plugin/src/ui.html) 의 `registerBinding()`
은 `fileKey && !bindingRegistered` 일 때만 발사되고, 성공 시
`bindingRegistered=true`. 이후 백엔드가 바인딩을 잃어도(재인제션 그래프
wipe, uvicorn `--reload` 재시작) 플래그가 true 라 재등록 안 함.
`disconnect()` 는 플래그를 안 지우므로 **플러그인 전체 재시작(페이지
리로드)** 만 `false` 로 리셋 → 그때만 재등록됨.

추가 desync: **fileKey 가 비면** "연결됨" 으로 보여도 announce-support·
poll·registerBinding 전부 스킵 → 백엔드 `connected: []` 로 완전히 깜깜.
(`figma.fileKey` 는 미게시/dev 파일에서 null → File Key 수동 입력 필요.)

### 적용한 수정 (2026-06-02)
바인딩 등록을 메타데이터처럼 **자가복구** 시킴:
- [figma_plugin_ws.py](../../api/features/ingestion/figma_plugin_ws.py)
  `/poll` 응답에 `bound: bool` 추가 (active FigmaBinding 의 figmaFileKey 가
  이 file_key 와 일치하는지). 매 poll 마다 싱글톤 lookup — 가벼움.
- [figma-plugin/src/ui.html](../../figma-plugin/src/ui.html): poll 콜백에서
  `data.bound === false` 면 `bindingRegistered=false` 리셋 후
  `registerBinding()` 재발사. `bindingInFlight` 가드로 3초 poll 동안 중복
  POST 방지. `registerBinding` 은 `.finally` 로 플래그 해제. → 백엔드가
  바인딩을 잃어도(재인제션 wipe·reload) 다음 poll 에 **재시작 없이 자동
  재등록**. `dist/plugin.js` 리빌드함(`bun build.js`).
- `data.bound === false` 는 strict 비교 → 구버전 백엔드(필드 없음)는
  스푸리어스 재등록 안 함.

남은 선택지(미적용): fileKey 빈 상태에서 "연결됨" 대신 "파일키 필요" 표시
(오해 소지 개선). 필요 시 추가.

---

## 10. Design 저장이 빈약한 sceneGraph 로 리치 콘텐츠 덮어씀 (HIGH — 데이터 손실) — ✅ FIXED 2026-06-02

### 증상
편집·저장·표시까지 정상인 UI 가, **새로고침 후 다시 열면 비어 있음.**
"자동납부 신청 상세" 가 이 상태 — Neo4j 의 sceneGraph 가 39노드/21텍스트
→ **5노드(FRAME 4 + CANVAS)/0텍스트** 로 덮어써짐. (Figma 에는 정상
반영돼 있어 pull 로 복구는 가능하지만, **사라진 것 자체가 버그.**)

### 원인
[InspectorPanel.vue#onDesignSave](../../frontend/src/features/canvas/ui/InspectorPanel.vue):
에디터의 `serializeSceneGraph` 는 가끔 **bare frame skeleton** 만 출력함
(DOCUMENT→FRAME collapse, leaf 드롭) — store 재빌드/탭전환 remount 레이스
중. 이를 막는 merge 안전망이 있지만, merge 는 `existing`(= `n.data.sceneGraph`)
을 읽을 수 있을 때만 동작. **저장 순간 `n.data.sceneGraph` 가 일시적으로
비어 있으면**(remount/refetch 레이스) `existing={}` 로 읽혀 merge 가 no-op
→ 빈약한 출력이 그대로 영속 → 리치 콘텐츠 소실.

### 1차 수정 (효과 없었음)
`onDesignSave` 에 leaf-less overwrite 가드 추가 — 그러나 **재현 지속**.
저장은 정상 통과하는데도 새로고침하면 빈 상태. → 범인은 에디터 저장이
아니었음.

### 진짜 원인 (2026-06-02, 피드백 루프)
영속된 degraded 그래프의 노드 ID 가 **`0:1`,`0:3` (Figma ID 형식)** →
Figma 에서 역수입된 것. 추적 결과 **plugin 의 `documentchange` 자동 export
피드백 루프**:
1. Save & Sync → backend `update-frame` → plugin 이 **Figma 프레임을 수정**.
2. 그 변경이 plugin 의 [`figma.on('documentchange')`](../../figma-plugin/src/plugin.ts)
   를 깨움 → debounce 후 `AUTO_EXPORT` → `reportExportResult` →
   `POST /api/figma-plugin/export-result`.
3. [export-result](../../api/features/ingestion/figma_plugin_ws.py) 는 프레임을
   **컴포넌트 인스턴스로 재추출 + 재렌더** → plain TEXT 드롭 → degraded
   sceneGraph → `frame_name` 매칭으로 **Neo4j 덮어씀**.
→ RA 가 방금 저장한 rich 데이터를 RA 자신의 push 가 유발한 auto-export 가
clobber. **#7 이 금지한 "auto Figma→RA sync 가 풍부 로컬을 덮음"** 의
잔존 경로(폴링 대신 plugin push 형태).

### 적용한 수정 (2층 방어)
1. **plugin** ([plugin.ts](../../figma-plugin/src/plugin.ts)):
   `documentchange` 자동 export 비활성화 (`AUTO_EXPORT_TO_RA = false`).
   Figma→RA 는 명시적 "가져오기"(pull) 만 (#7 정책). `dist/plugin.js` 리빌드.
2. **backend** ([figma_plugin_ws.py](../../api/features/ingestion/figma_plugin_ws.py)):
   `export-result` 가드 — figma 메타데이터(figmaNodeId/fileKey)는 항상
   갱신하되, **들어온 그래프의 TEXT 수가 기존보다 적으면 sceneGraph 는
   덮어쓰지 않음**(`write_sg = new_text >= existing_text`, Cypher CASE).
   AUTO_EXPORT 외 다른 lossy export 경로도 방어. (단위 검증 완료.)

(프론트의 1차 leaf-less 가드도 유지 — transient 빈 직렬화 방어용 보강.)

---

## 작업 우선순위 정리

| # | 작업 | 우선순위 | 담당 영역 |
|---|---|---|---|
| 1 | 텍스트 박스 클리핑 | ✅ DONE (2026-06-02) | open-pencil submodule |
| 3 | 빈 sceneGraph (9 UI) | ✅ DONE (2026-06-02) | wireframe agent prompt + content gate |
| 2 | FrameEditor desync | ✅ DONE (2026-06-02) | open-pencil submodule (provide proxy) |
| 5 | 워커 freeze 근본 픽스 | ✅ DONE (2026-06-02) | api 비동기화 (render/LLM async) |
| 4 | FramePreviewChat 미커밋 | ✅ DONE (2026-06-02) | placeholder 파일 생성 + alias 제거 |
| 6 | 인스펙터 UI 마무리 | 🟢 LOW | DONE |
| 7 | 자동 sync 회귀 방지 | 🟢 LOW | DONE |
| 8 | bulk 생성 LLM 429 | ✅ DONE (2026-06-02) | LLM 동시성 cap + 429 backoff |
| 9 | 플러그인↔RA 바인딩 desync | ✅ DONE (2026-06-02) | plugin self-heal re-register |
| 10 | Design 저장 콘텐츠 손실 | ✅ DONE (2026-06-02) | leaf-less overwrite 가드 |

이 세션에서 #6, #7 처리 완료. 2026-06-02 에 #1(렌더러 클립)·#3(빈 sceneGraph
프롬프트+콘텐츠 게이트)·#8(LLM 429 동시성 cap+backoff) 해결. #2, #4, #5 는 별도 PR.
