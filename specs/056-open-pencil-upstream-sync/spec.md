# Feature 056 — open-pencil upstream 동기화 + 컴포넌트 생성 고도화 + Proposal 스토리보드

## 배경
- `open-pencil/` 서브모듈은 `jinyoung/open-pencil` fork(2026-04-10 분기, 2026-05-07 마지막 커밋)이며 upstream `open-pencil/open-pencil` master(2026-09-03)와 약 1,491 커밋 차이가 있다.
- fork 커스텀은 (a) `packages/cli/src/wireframe-service.ts` — 컴포넌트 라이브러리(.fig) 카탈로그 + JSX/컴포넌트 배치 렌더 HTTP 서비스, (b) `src/federation/*` — robo-architect Inspector 에 임베드되는 FrameEditor/AIChat/FullPageEditor/FramePreview + sceneGraph JSON 브리지, (c) core 견고성 패치(boundVariables/pluginData 가드, 폰트 재등록, fig export 컴포넌트 GUID).
- spec 024 lessons-learned L4: open-pencil `<Instance>` JSX 가 동작하지 않아 `$INSTANCE:Name|k=v` 마커 + 백엔드 `retype_instance_markers` 우회를 사용 중.

## 목표 (What & Why)
### US1 — upstream 동기화
서브모듈을 upstream master 기반 브랜치(`robo-upstream-sync`)로 올리고 fork 커스텀을 새 패키지 구조(`@open-pencil/scene-graph`, `@open-pencil/fig`, `@open-pencil/kiwi`, `@open-pencil/pen`, `@open-pencil/dom-css`, `#core/*`)에 맞춰 재이식한다. 기존 Neo4j 에 저장된 sceneGraph JSON 포맷(`nodes: Record<id,node>`, `images: base64`)은 그대로 읽고 쓸 수 있어야 한다.

### US2 — 네이티브 `<Instance>` 기반 컴포넌트 생성
wireframe-service 렌더 경로에서 LLM 이 `<Instance component="Name" variantProp="v" overrides={{ 'label:text': '...' }} />` 를 직접 출력하도록 프롬프트를 바꾸고, 컴포넌트 카탈로그에 variant 속성/오버라이드 가능 자식을 포함한다. Figma 바인딩 모드(`figma-with-components`)는 컴포넌트가 렌더 그래프에 없으므로 마커 방식을 유지하되, 마커 레거시 입력도 계속 처리한다.

### US3 — Proposal 초안 단계 스토리보드
Proposal 초안이 제시될 때(설계·디자인 정합 완료 이전) 초안의 유저 저니를 open-pencil 로 생성한 화면 프레임 시퀀스(스토리보드)로 즉시 보여준다. 결과는 시연 영상으로 기록한다.

## 수용 기준
- AC1 `bun run build:packages` 및 robo-architect `frontend` vite 빌드가 통과한다.
- AC2 wireframe-service `/render` 에 `<Instance component=… />` JSX 를 보내면 INSTANCE 노드가 포함된 sceneGraph 가 반환되고, `$INSTANCE:` 마커 JSX 도 기존과 같이 동작한다.
- AC3 `/components?format=prompt` 에 variant 속성이 포함된다.
- AC4 InspectorPanel Design 탭에서 FrameEditor 가 기존 sceneGraph 로 렌더되고 저장이 동작한다(playwright).
- AC5 Proposal 초안 화면에 스토리보드 섹션이 나타나고 프레임이 렌더된다(playwright, 영상 기록).
