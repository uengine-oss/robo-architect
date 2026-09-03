# Plan 056

## 기술 결정
- 서브모듈 브랜치 `robo-upstream-sync` = `upstream/master@cb7ceea6` + 재이식 커밋. 이전 fork 는 `robo-fork-legacy` 브랜치로 보존.
- frontend vite alias 는 upstream `vite/aliases.ts#createOpenPencilAliases` 를 재사용하고, `@`/`#core` 는 importer 경로 기준으로 분기하는 기존 플러그인을 유지.
- 직렬화 브리지(`src/federation/bridge/serialize.ts`)는 기존 JSON 포맷 유지. `instanceIndex`/`enabledLibraries` 등 신규 필드는 역직렬화 시 재구성.
- federation 컴포넌트는 `createEditorStore`(`@/app/editor/session/create`) + `setActiveEditorStore` + `createTab`(ChatPanel 이 `activeTab` 을 요구) 조합으로 스토어를 격리한다.
- 백엔드: `component_library.build_jsx_agent_extra_context(native_instances=True)` 로 네이티브 Instance 프롬프트를 생성. `retype_instance_markers` 는 유지(레거시/Figma 모드).
- Proposal 스토리보드: 초안 생성 직후 화면 목록을 추출해 `wireframe_agent.run_render_agent` 로 프레임별 sceneGraph 를 만들고, 프론트 `ProposalStoryboard.vue` 가 `FramePreview` 로 나열.

## 구조
- open-pencil/packages/cli/src/wireframe-service.ts (port)
- open-pencil/src/federation/{FrameEditor,AIChat,FullPageEditor,FramePreview}.vue, bridge/* (port)
- open-pencil/packages/core/src/canvas/renderer/colors.ts, color/okhcl.ts (guard patch)
- frontend/vite.config.js, frontend/src/features/aiDesign/bootstrap.js
- api/features/figma_binding/component_library.py, api/features/ai_design/wireframe_agent.py
- api/features/proposal/* (storyboard), frontend/src/features/proposal/* (storyboard UI)
