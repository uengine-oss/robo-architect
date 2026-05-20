# Spec 024 Quickstart

Manual smoke scenarios — each can be reproduced from a clean dev environment in roughly five minutes.

## Pre-flight (one-time per session)

1. Backend running with autoreload:
   ```bash
   .venv/bin/uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
   ```
2. Frontend dev server:
   ```bash
   cd frontend && npm run dev   # vite at http://localhost:5173
   ```
3. open-pencil wireframe service:
   ```bash
   # check
   curl -s http://localhost:7610/health
   ```
4. Active Figma binding (verify):
   ```bash
   curl -s http://127.0.0.1:8000/api/figma-binding | python -m json.tool
   ```
5. Figma plugin running, Backend URL set to `http://localhost:8000` (Figma Desktop) or the active tunnel URL (Figma web). Plugin status indicator green.
6. At least one component scanned (skip if `componentCount > 0`):
   ```bash
   curl -s -X POST -H 'Content-Type: application/json' \
     -d '{"apiToken":"figd_..."}' \
     http://127.0.0.1:8000/api/figma-binding/components/scan
   ```

---

## S1 — Scan the bound file's component library

**Goal:** confirm scanner + VLM round-trip persists `:FigmaComponent` rows.

1. Open the binding modal (top menu Figma button → 연결 상태 tab).
2. Locate "디자인 시스템 컴포넌트" panel, click **컴포넌트 스캔**.
3. Wait ≤ 30 s (VLM concurrency 3 × N components).
4. Toast should show "추가 N / 갱신 0 / 제거 0 — VLM 성공 N / 실패 0".
5. Verify in Neo4j:
   ```cypher
   MATCH (c:FigmaComponent) RETURN c.name, c.pageName, c.vlmDescription LIMIT 20
   ```
6. Confirm `GET /api/figma-binding` now returns `componentCount: N`.

**Pass criteria:** every COMPONENT/COMPONENT_SET in the bound file has a row with non-empty `vlmDescription`. UI toggle "Figma + Components" becomes enabled.

---

## S2 — Empty-catalog gating

**Goal:** confirm the toggle is disabled when no components are scanned.

1. Click "카탈로그 비우기" in the binding modal.
2. Open the requirements ingestion modal.
3. Verify the "Figma + Components" tab is disabled with hover tooltip "바운드 파일에 컴포넌트 없음 — 먼저 스캔하세요".

---

## S3 — Dev-mode mixed wireframe (instance + native primitives)

**Goal:** confirm the JSX agent + post-processor + plugin pipeline draws a real layout in Figma.

This is the canonical reproduction; automated via Playwright at `tests/playwright-mixed-mode-e2e.py`.

1. Re-scan if needed (S1).
2. Open the binding modal, locate "샘플 와이어프레임 생성" panel.
3. Brief field default already describes the product-search screen; edit if desired.
4. Click **와이어프레임 생성** (10–30 s LLM + render + plugin push).
5. Toast: `✓ 생성 완료 — page <name>, instance 2 / native ≥3 · plugin nodesCreated=K, failed=0`.
6. Figma viewport auto-centers on the new frame. Verify visually:
   - Search input (INSTANCE of `Component 2`) at top.
   - Result list rows in the middle (custom TEXT primitives).
   - "장바구니에 추가" button (INSTANCE of `Component 1`) at bottom.
   - No empty boxes, no "Unsupported node type" log lines.

**Pass criteria:** `nodesFailed: 0`, `renderErrors: []`, frame visibly populated.

---

## S4 — Production ingestion-mode parity

**Goal:** confirm the figma-with-components ingestion mode produces equivalent results when a real PRD is uploaded.

1. Open the requirements ingestion modal.
2. Select UI 생성 = "Figma + Components".
3. Paste a small PRD that mentions search/list/buttons.
4. Upload. Watch the SSE log for `ingestion.ui_wireframe.figma_components.success` events with `instances=N`.
5. Open the generated `:UI` node in Inspector; verify the stored `sceneGraph` contains INSTANCE leaves with `componentId` set.
6. Trigger Figma full-sync; confirm Figma frames match the sceneGraph.

**Pass criteria:** generated UIs use the catalog where appropriate AND fall back to JSX-rendered primitives where no catalog entry fits. Unresolved component names log as warnings but do not abort the run.

---

## S5 — Degraded paths

**S5a** — open-pencil service down: stop the Bun service. Trigger S3. Expected: dev endpoint returns `{ok: false, step: "run_render_agent_failed"}` with an informative summary.

**S5b** — Plugin disconnected: close the plugin window. Trigger S3. Expected: 503 with `messageKr: "Figma 플러그인이 연결되어 있지 않습니다."`.

**S5c** — Catalog has the requested name but the local file no longer contains that COMPONENT: rename `Component 2` in Figma to `Component 2 (renamed)` without rescanning. Trigger S3. Expected: plugin substring-matches "component 2" against "component 2 (renamed)" and instantiates it. (If rename is too divergent the plugin reports `INSTANCE "X": component not found` in `renderErrors`.)

---

## Reference

- Constitution §VIII, §IX: `.specify/memory/constitution.md`.
- Trial-and-error log: `lessons-learned.md` (same folder).
- E2E: `tests/playwright-mixed-mode-e2e.py`.
- Unit/integration tests: `api/features/figma_binding/tests/`, `api/features/ingestion/tests/`.
