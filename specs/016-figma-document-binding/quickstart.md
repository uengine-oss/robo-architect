# Quickstart — Figma Document Binding (manual smoke test)

End-to-end manual verification of US1 → US2 → US3. Run after `/speckit-implement` completes its tasks. Replace placeholders in `<...>`.

## Prerequisites

- Backend running (`uv run uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload`).
- Frontend running (`cd frontend && npm run dev`).
- Neo4j up; schema applied (`docs/cypher/schema/01_constraints.cypher`, `02_indexes.cypher`, including the new `:FigmaBinding`, `:StoryboardPageMapping`, `:BindingHistoryEvent` constraints).
- An Event Modeling project loaded with at least 2 storyboards (= 2 user-initiated entry commands; visible in the left-panel `BUSINESS PROCESSES` list) and at least 1 UI node reachable from each.
- A Figma file you can edit, plus a personal access token.
- The Figma plugin (`figma-plugin/`, manifest `id: robo-architect-sync`) installed and running inside Figma desktop, with the target file open. The plugin's REGISTER message must include `supportedMessages` containing `CREATE_PAGE` and `CREATE_FRAME_IN_PAGE`.

## Step 1 — Connect (US1)

1. Open `http://localhost:5173/`.
2. Click the new **Figma** button in the top bar (between `PRD 생성` and `Claude Code`).
3. In the modal, paste the Figma file URL or key, paste the access token, click **Connect**.
4. **Expected**: Modal shows "Connected"; the top-bar Figma button now displays `Connected · <filename>`. `GET /api/figma-binding` returns the binding JSON. Reload the page → indicator persists.
5. **Failure case**: Wrong token → modal shows the Korean error from `POST /connect`; binding is *not* persisted (`GET /api/figma-binding` still 404).

## Step 2 — Storyboard page sync (US2)

1. With the Figma file open in Figma, observe the page list (left sidebar in Figma).
2. In the modal, click **Sync storyboards** (or it auto-runs the first time after Connect).
3. Within 5 seconds, one new page per storyboard appears in Figma, named after each entry command's display name (e.g. `상품 등록`, `주문하기`, `장바구니에 상품 추가`).
4. Re-click **Sync storyboards** → response shows `created: []`, `reused: [...]` (idempotent).
5. **Rename a storyboard** locally (rename the entry Command's displayName in the canvas) → trigger sync again → response shows the rename in `renamed: [...]`. (Actual Figma page rename is best-effort; in v1 only the cached `figmaPageName` is updated and the Figma page name itself stays — this is a known limitation called out in research D5; will be revisited when the plugin grows a `RENAME_PAGE` op.)
6. **Remove a storyboard locally** (delete its entry command, or convert it to a policy-invoked command) → next sync archives the mapping; the Figma page is left intact.

## Step 3 — Generate UI to Figma (US3)

1. Select a UI node that has no design yet AND is reachable from at least one entry command. Open the Inspector → **Design** tab.
2. Click **Component로 생성** (or **OpenPencil AI로 생성**).
3. **Expected**: a generation status panel streams phases (`wireframe.start` → `wireframe.done` → `figma.send` → `figma.ack` → `persist.done` → `done`). The 202 response from `POST /generate-frame/...` includes the `resolvedStoryboard` so the UI shows "Generating into page: 상품 등록".
4. Switch to Figma → the new frame appears in the storyboard's page (the one whose name matches the resolved entry command's display name). The Inspector Design tab now shows that frame and the new `Linked to <file>/<page>/<frame>` badge.
5. Run `MATCH (u:UI {id:"<ui_node_id>"}) RETURN u.designSource, u.figmaPageId, u.figmaNodeId, u.figmaFileKey, u.figmaStoryboardCommandId` in Neo4j → all five fields populated, `designSource = "figma-bound"`.

### Step 3b — Conflict prompt (FR-012)

1. Pick a UI node that already has a `sceneGraph` from prior HTML generation.
2. Click **Component로 생성** while binding is active.
3. **Expected**: modal asks "Overwrite from Figma" / "Import existing into Figma".
4. Choose Import → a Figma frame is created from the current sceneGraph; the UI node's `designSource` becomes `imported`.
5. Choose Overwrite (on a different node) → fresh wireframe is generated and pushed; `designSource` becomes `figma-bound`.

### Step 3c — Orphan UI (D10)

1. Pick a UI node that is *not* reachable from any entry command (e.g. an orphaned UI you placed for testing).
2. Click **Component로 생성**.
3. **Expected**: `409` response with the Korean message "이 UI는 어떤 스토리보드에도 속하지 않아 Figma 페이지를 결정할 수 없습니다.". The frontend offers (a) generate without binding (HTML mode for this node only) or (b) cancel.
4. Verify a `:BindingHistoryEvent {eventType:"orphan_ui_blocked"}` row appears.

## Step 4 — Disconnect / Replace (US4)

1. Open the Figma button modal → **Disconnect**. Confirm in dialog.
2. **Expected**: top-bar indicator clears; `GET /api/figma-binding` returns 404; existing UI scene graphs and Figma frames remain intact.
3. Open the modal again → **Connect** to a different file. Confirm.
4. **Expected**: new file is bound, `sync-storyboards` runs against the new file; UI nodes with `figmaFileKey` from the previous binding now show a "from previous binding" badge in their Design tab.

## Step 5 — Failure modes

- **Plugin not running**: stop the Figma plugin. Click **Component로 생성** → `503` response with the Korean error; binding status flips to `unreachable`. Re-launch the plugin and retry → status returns to `active` on success.
- **Network drop during generate**: kill the backend mid-stream. Frontend shows `error` event with phase. Restart backend; the UI node remains in its prior state (no half-written sceneGraph).
- **Old plugin version**: simulate by stripping `CREATE_PAGE` from the plugin's REGISTER `supportedMessages`. Sync attempt → `503` with Korean error "Figma 플러그인이 최신 버전이 아닙니다. 업데이트 후 다시 시도해 주세요.".

## Cleanup

- `DELETE /api/figma-binding` to disconnect.
- Optional: `MATCH (b:FigmaBinding) DETACH DELETE b; MATCH (m:StoryboardPageMapping) DETACH DELETE m;` to fully reset for the next run.

## Step 6 — Reliability checks (FR-017, FR-018; v1.1 hardening)

Two automated diagnostics back the SC-007 / SC-008 acceptance bars. They are intentionally diagnostic (not full-TDD) — their job is to detect regressions in the retry stack and the font preload, not to enforce them on every PR.

### FR-017 / SC-007 — bulk Figma-mode generation

```
cd frontend && npx playwright test tests/figma-ui-bulk-diag.spec.ts --reporter=line
```

What it does:

1. Opens `요구사항 문서 업로드` → `텍스트 입력` → `샘플 요구사항 사용`, switches `UI 생성` to `Figma UI`, clicks `분석 시작`, confirms `삭제하고 계속`.
2. Hooks `window.EventSource` so it can read every `progress` event from the ingestion SSE stream (the backend never sends an explicit `done`; we exit on `phase=complete` + `progress=100` after a 6 s grace).
3. Counts UI events whose `data.object.sceneGraph` length ≥ 50 chars as "populated" and the rest as "empty".

**Pass**: every emitted UI is `populated` (run takes ~7 minutes on a developer laptop). Pre-fix baseline: 11 / 19 populated. Post-fix: 19 / 19. A regression here means a layer of the retry stack (transport-level, agent-loop fallback, or wrapper retry) has been removed or broken.

Fast cross-check via Neo4j (no Playwright required):

```
MATCH (u:UI)
RETURN count(u) AS total,
       count(CASE WHEN u.sceneGraph IS NOT NULL AND u.sceneGraph <> '' THEN 1 END) AS populated
```

### FR-018 / SC-008 — Korean text in the FrameEditor

```
cd frontend && npx playwright test tests/font-loading-diag.spec.ts --reporter=line
```

What it does:

1. Loads the app, expands the canvas tree, opens the first UI node's `Design` tab.
2. Probes `/Inter-Regular.ttf`, `/NotoNaskhArabic-Regular.ttf`, `/canvaskit.wasm`, plus the Google Fonts metadata API (to document the 429 baseline that motivated the fix).
3. Captures CanvasKit / OTS console messages and screenshots the canvas.

**Pass**: `/Inter-Regular.ttf` returns ≥ 100 KB of real TTF (not the 744-byte SPA fallback), no `OTS parsing error` / `Failed to load font "Inter"` console messages, and the screenshot at `frontend/test-results/font-diag.png` shows Korean labels rendered on the canvas. A regression here means either the bundled fonts went missing from `frontend/public/` or the Pretendard preload in `frontend/src/main.js` was removed.
