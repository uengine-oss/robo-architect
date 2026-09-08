# 056 구현 노트 — upstream 이식에서 실제로 걸린 것들

**작성**: 2026-09-04 · spec 024 `lessons-learned.md`와 같은 형식(증상 → 진단 → 조치)

다음 동기화 때 같은 곳에서 다시 막히지 않도록, 커밋만 봐서는 안 보이는 것들을 남긴다.

---

## L1. v0.14 패키지 분리 — `@open-pencil/core` 한 곳에서 다 가져올 수 없다

- **증상** — federation 파일들이 `import { SceneGraph } from '@open-pencil/core'`로 시작하는데,
  타입 체크가 "declares locally, but it is not exported"로 줄줄이 실패.
- **진단** — v0.14.0 breaking change. scene graph 타입·기하·스냅·undo는 `@open-pencil/scene-graph`,
  `.pen`은 `@open-pencil/pen`, kiwi 압축은 `@open-pencil/kiwi`, `.fig` 노드 변환은 `@open-pencil/fig`,
  HTML/CSS는 `@open-pencil/dom-css`로 나갔다. `@open-pencil/core`는 렌더러·레이아웃·도구·design-jsx만 남았다.
- **조치** — 이식 규칙을 이렇게 고정했다.
  - `SceneGraph`, `SceneNode`, `GeometryPath`, `generateId`, `setInstanceOverride` → `@open-pencil/scene-graph`
  - `createDefaultNode` → `@open-pencil/scene-graph/node-defaults`
  - `computeAllLayouts` → `@open-pencil/core/layout`
  - `renderJSX`, `exportFigFile`, `fontManager` → `@open-pencil/core`
- **주의** — Bun 런타임은 `@open-pencil/scene-graph/instance-overrides` 같은 **서브패스를 못 찾는다**
  (package.json `exports`에 없다). 배럴(`@open-pencil/scene-graph`)에서 가져와야 한다.
  vite는 alias 덕에 통과하므로 타입체크만 믿으면 런타임에서 터진다.

---

## L2. 사라진 파일에 의존하던 federation

- **증상** — 이전 fork의 federation 4종이 `@/stores/editor`, `@/composables/use-chat`,
  `@/components/Toolbar.vue`를 import하는데 upstream에 그 경로가 없다.
- **진단** — upstream이 `src/app/**` 구조로 재편했다. 대응은 이렇다.

  | 이전(fork) | upstream master |
  |---|---|
  | `@/stores/editor` → `createEditorStore`, `setActiveEditorStore` | `@/app/editor/session` (create) + `@/app/editor/active-store` (setActive) |
  | `@/composables/use-chat` → `useAIChat` | `@/app/ai/chat/use` |
  | `@/composables/use-keyboard` | `@/app/shell/keyboard/use` |
  | `@/components/Toolbar.vue` | `@/components/Toolbar/Toolbar.vue` |

- **조치** — federation을 `createEditorStore(graph)` → `setActiveEditorStore(store)` →
  `provideEditor(store)` 세 줄로 시작하도록 통일했다. upstream의 패널들은 전부
  `useEditorStore()`(active-store 프록시)로 스토어를 찾으므로, 이 세 줄만 맞으면 나머지는 그대로 붙는다.
- **주의** — `store`를 `ref()`에 담으면 안 된다. 에디터 스토어는 함수 260여 개를 가진 큰 객체라
  깊은 반응형으로 감싸면 타입도 안 맞고 성능도 나쁘다. `shallowRef()`를 쓴다.

---

## L3. `instanceOverrides`가 JSON에서 조용히 사라진다

- **증상** — 컴포넌트 인스턴스의 텍스트 오버라이드가 저장 후 다시 열면 없어진다. 에러는 없다.
- **진단** — upstream의 `instanceOverrides`는 `{self: Map, descendants: Map<string, Map>}`이다.
  `JSON.stringify(Map)`은 `{}`가 된다 — 조용히 빈 객체로 저장된다.
- **조치** — 브리지와 렌더 서비스 양쪽에서 upstream 헬퍼를 쓴다.
  `serializeInstanceOverrideState()` → 배열 형태, `deserializeInstanceOverrideState()` → Map 복원.
  이 헬퍼는 legacy 평범한 객체와 undefined도 받아준다.
- **교훈** — 노드 필드에 Map/Set이 들어오면 직렬화 경로를 반드시 다시 본다.
  같은 이유로 `textPicture`(CanvasKit 핸들)는 직렬화에서 **제외**한다.

---

## L4. `<Instance>`는 되는데 `Property 1` 변형이 안 골라진다

- **증상** — `<Instance component="header-main-ios" Property 1="Default" />`가 JSX 파싱 에러
  (`Unexpected token (32:50)`). 속성명에 공백이 있으면 JSX 어트리뷰트로 쓸 수 없다.
- **진단** — Figma에서 온 COMPONENT_SET의 변형 속성명이 `Property 1`, `header-main` 같은 형태다.
  upstream `findVariantInSet()`은 props를 그대로 훑기 때문에 이런 이름은 전달할 방법이 없었다.
- **조치** — upstream `renderer.ts`에 `variant={{ "Property 1": "Default" }}` 객체를 추가로 읽도록
  패치했다(개별 prop 방식도 그대로 동작). 카탈로그 프롬프트에도 두 문법을 함께 안내한다.
- **참고** — 라이브러리 1,122개 컴포넌트 중 543개가 COMPONENT_SET이고, 상당수가 공백 있는
  속성명을 쓴다. 이 패치 없이는 변형 선택이 사실상 불가능하다.

---

## L5. 오버라이드 키를 LLM이 `label:text` 형태로 안 쓴다

- **증상** — 프롬프트에 `overrides={{ "label:text": "…" }}`라고 써놨는데 모델이
  `overrides={{ text: "…" }}`, `{{ title: "…" }}`로 낸다. upstream은 `:`가 없는 키를 무시한다.
- **진단** — 모델 탓만 할 일이 아니다. 컴포넌트마다 자식 이름이 다르고(`label`, `본문`, `{title text}`)
  모델이 그걸 정확히 맞히길 기대하는 건 무리다.
- **조치** — 서비스가 렌더 **전에** 정규화한다(`normalizeOverrideKeys`).
  라이브러리에서 그 컴포넌트의 실제 TEXT 자식 이름을 모아, `:` 없는 키는
  ① 이름 완전일치 ② 대소문자 무시 일치 ③ 부분 일치 ④ `text`/`label`/`title`/`placeholder` 같은
  느슨한 키는 첫 TEXT 자식, 순으로 붙여준다. 마커(`|text=…`) 경로도 같은 함수를 탄다.
- **교훈** — LLM 출력 형식을 프롬프트로만 강제하지 말고, 받는 쪽에서 관대하게 정규화한다.

---

## L6. 아이콘 하나가 화면 전체를 죽인다

- **증상** — 스토리보드 4화면 중 "장바구니"만 500. 서비스 로그에
  `TypeError: undefined is not an object (evaluating 'data.icons[iconName]')`.
- **진단** — `<Icon name="lucide:shopping-cart" />` 같은 요소를 만나면 renderJSX가 Iconify API를
  호출한다. 응답에 `icons` 키가 없거나(알 수 없는 prefix) 네트워크가 막히면 예외가 나고,
  그 예외가 **렌더 전체**를 취소한다. 화면 하나에 아이콘이 스무 개면 실패 확률이 그만큼 커진다.
- **조치** — 두 겹으로 막았다.
  1. `icons/index.ts` — fetch 실패·`icons` 부재를 "없음"으로 처리(throw하지 않음).
  2. `renderer.ts` `renderIconNode()` — 아이콘을 못 찾으면 던지지 말고 **같은 크기의 반투명 ELLIPSE**
     를 놓는다. 이름은 `icon:<요청한 이름>`으로 남겨 나중에 교체할 수 있게 한다.
- **교훈** — 와이어프레임은 "대략 맞는 그림"이 목적이다. 장식 요소 하나 때문에 전체를 잃지 않는다.

---

## L7. CanvasKit 버전 불일치 — `r.ck.PathBuilder is not a constructor`

- **증상** — Playwright에서 편집기를 열면 이 예외로 캔버스가 비어 있다. dev에서는 화면이 뜨는데
  편집기만 안 됐다.
- **진단** — 프론트엔드 `node_modules/canvaskit-wasm`은 0.40.0, open-pencil은 0.41.1.
  vite는 JS를 프론트엔드 것(0.40)으로 묶고, `public/canvaskit.wasm`도 0.40이었는데,
  upstream 렌더러는 0.41에서 생긴 `PathBuilder` API를 쓴다.
- **조치** — 두 가지를 한다.
  1. vite alias에 `canvaskit-wasm` → open-pencil의 것으로 고정.
  2. wasm 복사 플러그인이 open-pencil의 `bin/canvaskit.wasm`을 **매 빌드 덮어쓰기**
     (기존에는 `!existsSync(dest)`라 오래된 파일이 남아 있었다).
- **교훈** — wasm과 그것을 부르는 JS는 한 쌍이다. 어느 한쪽만 갱신하면 조용히 어긋난다.

---

## L8. upstream 앱이 요구하는 컴파일 상수·플러그인

호스트(robo-architect) vite에 없어서 순차적으로 터진 것들. 전부 upstream `vite.config.ts`에 있다.

| 증상 | 원인 | 조치 |
|---|---|---|
| `does not provide an export named 'markFontLoaded'` | v0.14에서 폰트 API가 `fontManager` 싱글턴(FontManager 클래스)으로 이동 | `fontManager.markLoaded(family, style, buf, 'bundled')` / `fontManager.setCJKFallbackFamily(...)` |
| `__OPENPENCIL_LOCAL_AUTOMATION_HTTP_URL__ is not defined` | upstream이 `define`으로 주입하는 컴파일 상수 4개 | 호스트 vite `define`에 동일 키 추가(자동화 토큰은 `null`) |
| `Expected ';' … design-context.md` | `src/app/ai/**/*.md`를 raw 문자열로 import | upstream `vite/raw-markdown.ts` 플러그인 재사용 |
| `Rollup failed to resolve "/favicon-32.png"` | `AppMenu.vue`가 루트 절대경로 이미지를 참조 | 자산 복사 플러그인에 `public/icons` 후보 추가 + `public/favicon-32.png` 배치 |

---

## L9. Playwright — 이 저장소의 testId 속성은 `data-test-id`

- **증상** — `getByTestId('proposal-storyboard')`가 계속 못 찾는데 화면에는 분명히 렌더돼 있었다
  (실패 스크린샷에 스토리보드가 그대로 찍혀 있었다).
- **진단** — Playwright 기본 testId 속성은 `data-testid`(하이픈 없음). 이 저장소와 open-pencil은
  **`data-test-id`**를 쓴다.
- **조치** — 스토리보드 전용 config에 `use.testIdAttribute: 'data-test-id'`를 넣었다.
  새 spec 파일을 만들 때마다 확인할 것.
- **덤** — 실패 시 `test-failed-1.png`를 먼저 본다. "요소를 못 찾음"이 "기능이 안 됨"을 뜻하지 않는다.
  이번 건은 기능이 멀쩡했고 셀렉터만 틀렸다.

---

## L10. 워크트리 스택은 포트가 겹친다

- **증상** — 워크트리 프론트(5174)가 "서버 연결 실패"를 띄우고 Proposal 목록이 비어 있었다.
- **진단** — `frontend/vite.config.js`의 dev 프록시가 `127.0.0.1:8000` 고정이었다. 워크트리 백엔드는
  8310에 떠 있었고, 8000에는 **다른 체크아웃의 백엔드**가 살아 있어서 404만 돌아왔다.
- **조치** — 프록시 타깃을 `process.env.VITE_API_PROXY || 'http://127.0.0.1:8000'`으로 바꿨다.
  워크트리에서는 `VITE_API_PROXY=http://127.0.0.1:8310 npx vite --port 5174`로 띄운다.
- **덤** — 셸에 오래된 `NEO4J_PASSWORD`가 export돼 있으면 `.env`보다 우선한다.
  스크립트는 `env -u NEO4J_PASSWORD ...`로 실행하고, 단독 실행 스크립트에는 `load_dotenv()`를 넣는다.

---

## 다음 동기화 때 확인할 목록

1. `src/app/editor/session`·`src/app/editor/active-store`·`src/app/ai/chat/use` 경로가 살아 있는가
2. `SceneNode`에 새 필드가 생겼는가 → `bridge/serialize.ts`의 `createDefaultNode` 보강으로 흡수되는가
3. Map/Set 타입 필드가 추가됐는가 → 직렬화 헬퍼 필요
4. `canvaskit-wasm` 버전이 올랐는가 → alias + `public/canvaskit.wasm` 동시 갱신
5. `vite.config.ts`의 `define`·플러그인 목록이 늘었는가
6. `design-jsx/renderer.ts`의 두 패치(`variant` 객체, 아이콘 플레이스홀더)가 upstream에 반영됐는가
   — 반영됐으면 로컬 패치를 지운다
