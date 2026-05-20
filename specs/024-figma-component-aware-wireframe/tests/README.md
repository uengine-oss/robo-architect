# Spec 024 Tests

Two layers of automated verification for the figma-component-aware wireframe feature:

## 1. Unit / integration (pytest)

Lives in the canonical feature folders so `pytest` discovery works without flags:

| File | Coverage |
|---|---|
| `api/features/figma_binding/tests/test_component_library.py` | Scanner orchestrator, catalog formatter, name → figmaNodeId index, 404/409 paths |
| `api/features/figma_binding/tests/test_component_vlm.py` | VLM mock — empty URL, success, LLM failure, image download failure |
| `api/features/figma_binding/tests/test_repository_components.py` | `:FigmaComponent` Cypher CRUD parameter contract |
| `api/features/ingestion/tests/test_ui_generation_mode_validation.py` | `ui_generation_mode = "figma-with-components"` accepted on both upload routes |

Run:

```bash
./.venv/bin/python -m pytest api/features/figma_binding/tests api/features/ingestion/tests -q
```

22 tests, ~0.4 s.

## 2. End-to-end (Playwright, headed)

`playwright-mixed-mode-e2e.py` — drives the actual frontend (vite) → opens the Figma binding modal → fills the sample wireframe brief → clicks generate → waits for the Figma plugin to ack the new page+frame. Headed (visible Chromium window) with slow-mo so a human can watch each step.

This is the canonical reproduction for the user story "mixed-mode wireframe with both predefined components and custom primitives, end-to-end into Figma". Use it whenever:
- The spec 024 ingestion-phase mode (`figma-with-components`) is touched.
- The Figma plugin's `renderJsxSceneGraphIntoFrame` / INSTANCE handler / autolayout appliers are touched.
- The `retype_instance_markers` post-processor is touched.
- open-pencil's JSX runtime (`buildComponent` substitution) is upgraded.

### Run

Pre-flight checklist (constitution IX is the long version):

1. uvicorn launched with `--reload`:
   ```bash
   .venv/bin/uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload
   ```
2. vite dev server up:
   ```bash
   cd frontend && npm run dev
   ```
3. open-pencil wireframe service up (`http://localhost:7610/health` → `{status:"ok"}`).
4. Active Figma binding (`GET /api/figma-binding` returns 200 with non-null `figmaFileKey`).
5. Catalog scanned (`GET /api/figma-binding/components` shows ≥1 component).
6. Figma plugin window open + connected to the same backend (`POST /api/figma-binding/components/_dev/test-render` returns anything other than `step: create_page_timeout`).

Then:

```bash
./.venv/bin/python specs/024-figma-component-aware-wireframe/tests/playwright-mixed-mode-e2e.py
```

### Expected output

```
→ navigating http://localhost:5173
✓ result: ✓ 생성 완료 — page <name> (<nodeId>), instance N / native M · plugin nodesCreated=K, failed=0
```

Screenshots land in `tmp/spec024-playwright/01-home.png … 07-final.png` relative to the repo root.

### Knobs

| Env | Default | Effect |
|---|---|---|
| `RA_FRONTEND_URL` | `http://localhost:5173` | vite URL |
| `RA_SLOWMO_MS` | `300` | Delay per Playwright action (ms) |
