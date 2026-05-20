# Implementation Plan: Figma-Component-Aware Wireframe Generation

**Branch**: `figma-integration` · **Created**: 2026-05-12 · **Status**: Active
**Input**: spec.md (US1–US3 + FR-001..FR-011) and companion `research.md`, `data-model.md`, `contracts/rest-api.md`, `quickstart.md`.

## Summary

Extend the existing FigmaBinding (spec 016/020) with a component-library indexer and let the ingestion wireframe phase consume that catalog. The wireframe phase already exposes a `{component_catalog}` placeholder in `_UI_COMPONENT_SYSTEM_PROMPT_TEMPLATE` (`api/features/ingestion/workflow/phases/ui_wireframes.py:74-103`) currently filled by `open_pencil_client.get_component_catalog_for_prompt()` — we add a second source (`figma_binding.component_library.get_catalog_for_prompt()`) and switch on a new `ui_generation_mode = "figma-with-components"`.

## Technology

- **Python**: existing FastAPI + Pydantic + Neo4j + httpx + LangChain (no new deps).
- **Vue 3 (frontend)**: 2 modified components (`FigmaBindingModal.vue`, `RequirementsIngestionModal.vue`) and the `frontend/src/features/figmaBinding/api.js` REST wrapper.
- **VLM**: reuse `api/platform/llm.get_llm()` (vision-capable provider already in play via spec 014 image-to-wireframe). No new model env var; an optional `LLM_VISION_MODEL` override is honored if set.
- **Figma REST API**: reuse `api/features/ingestion/figma_api.py` thumbnail/file helpers — already 403/404/429-aware.

## Project Structure

```
api/features/figma_binding/
├── component_library.py          # NEW — scan + catalog format
├── component_vlm.py              # NEW — VLM single-sentence describer
├── repository.py                 # extend — :FigmaComponent CRUD
├── router.py                     # extend — /components/{scan,GET,DELETE}
├── service.py                    # extend — _to_response gains componentCount
└── tests/
    ├── test_component_library.py # NEW
    └── test_component_vlm.py     # NEW

api/features/ingestion/
├── router.py                     # extend — accept figma-with-components mode
├── ingestion_sessions.py         # extend — docstring/allowed set
├── workflow/phases/ui_wireframes.py  # extend — catalog source branch
└── tests/
    └── test_ui_generation_mode_validation.py  # NEW

frontend/src/features/figmaBinding/
├── api.js                        # extend — scanComponents, listComponents
└── ui/
    ├── FigmaBindingModal.vue     # extend — scan button + count
    └── FigmaButton.vue           # optional — componentCount badge

frontend/src/features/requirementsIngestion/ui/
└── RequirementsIngestionModal.vue # extend — 3-way toggle + gating
```

## Constitution Gates

- **I Neo4j SoT**: all component metadata lives in `:FigmaComponent`, no parallel store.
- **III Singleton-binding model**: scan/list endpoints operate on `:FigmaBinding {id:'singleton'}`. Multi-binding is out of scope.
- **VII Phase-boundary logging**: SmartLogger events at `figma_binding.components.scan.start/done`, `figma_binding.components.vlm.failed`, `ingestion.ui_wireframe.figma_components.{success,fallback,unresolved}`.
- **IX No new env var**: only the existing `LLM_VISION_MODEL` (already used by spec 014) is read.

## Decisions (frozen — see research.md for rationale)

| # | Decision | Choice |
|---|----------|--------|
| D1 | Scan trigger | Manual button in FigmaBinding modal |
| D2 | Library page identification | Any `CANVAS` containing `COMPONENT`/`COMPONENT_SET` |
| D3 | Empty-catalog handling | Frontend disables the toggle option (tooltip explains) |
| D4 | VLM concurrency | `asyncio.Semaphore(3)` |
| D5 | Scan API style | Synchronous POST (≤~150 components assumed); SSE deferred |
| D6 | Component-instance rendering | sceneGraph node carries `figmaNodeId` for plugin to instantiate; plugin-side `INSTANCE` handler is a separate PR but backend/frontend ship independently |

## Architecture flow

```
[FigmaBindingModal: 컴포넌트 스캔]
  → POST /api/figma-binding/components/scan {api_token}
    → service.scan_components()
      → repository.get_active_binding()
      → figma_api.GET /v1/files/{key}?depth=4    (existing helper pattern)
      → walk CANVASes, collect COMPONENT/COMPONENT_SET
      → figma_api.POST /thumbnails (existing)    → image URLs
      → component_vlm.describe(image_url[])      → {nodeId: sentence}
      → repository.upsert_figma_component(...)   * N
      → repository.delete_stale_figma_components(seen_ids)
    → ScanResponse{added, updated, removed, vlmFailures, componentCount}

[Ingestion upload]
  → POST /api/ingest/upload  {ui_generation_mode: "figma-with-components"}
    → session.ui_generation_mode = "figma-with-components"
    → ui_wireframes phase:
      _is_figma_with_components_mode(ctx) == True
      catalog = figma_binding.component_library.get_catalog_for_prompt()
      if catalog empty: fall back to _generate_jsx_scene_graph_for_figma_mode
      else: LLM(system=template.format(component_catalog=catalog), human=screen_brief)
            → JSON {components:[{component,overrides}]}
            → name→figmaNodeId lookup
            → SerializedSceneGraph with INSTANCE nodes
```

## Critical files

Bold = touched by this plan; (READ-ONLY) = referenced for reuse.

- **`api/features/figma_binding/repository.py`** — append :FigmaComponent CRUD + binding clear-on-replace hook.
- **`api/features/figma_binding/service.py`** — `_to_response` adds `componentCount`.
- **`api/features/figma_binding/router.py`** — three new routes.
- **`api/features/figma_binding/component_library.py`** *(new)*.
- **`api/features/figma_binding/component_vlm.py`** *(new)*.
- (READ-ONLY) `api/features/ingestion/figma_api.py:260-295` — `/thumbnails` reuse.
- (READ-ONLY) `api/features/model_modifier/routes/ui_wireframe_from_image.py:149-179` — VLM pattern reference.
- **`api/features/ingestion/router.py:61-64, 161-164, 193, 227-230`** — allowed-set update (2 sites).
- **`api/features/ingestion/ingestion_sessions.py:37-41`** — docstring + value list.
- **`api/features/ingestion/workflow/phases/ui_wireframes.py:189-266, 344-345, 506-520, 650-663`** — mode branch + catalog wire + INSTANCE serializer.
- **`frontend/src/features/figmaBinding/api.js`** — scanComponents/listComponents.
- **`frontend/src/features/figmaBinding/ui/FigmaBindingModal.vue`** — scan UI.
- **`frontend/src/features/requirementsIngestion/ui/RequirementsIngestionModal.vue:97-102, 1507-1525, 525-555`** — 3-way toggle + payload + gating.

## Out of scope

- Figma plugin-side `INSTANCE` node handler (separate PR).
- Incremental scan (`figmaNodeLastModified` is stored but unused at v1).
- Per-screen UI to manually pick components (LLM picks; humans don't override yet).
- Multi-binding catalogs.
