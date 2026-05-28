# Refactor Audit — Feature 031 Generation Language Policy

**Created**: 2026-05-28 (during T001/T002/T003)

Living document. Tick off each `[ ]` row as the corresponding refactor task completes. The AST regression test at `api/tests/regression/test_language_chokepoint.py` (T023) is the canonical enforcement; this file is the human-facing checklist.

---

## T001 — Backend `SystemMessage(content=...)` call sites (74 total, 49 files)

Discovered via `grep -rn "SystemMessage(content" api/features/ --include="*.py"` at HEAD `4be7137`. Counts: **74 call sites across 49 files**, distributed wider than the plan.md estimate (20 files). Refactor task groups (T011/T012/T019/T020/T021) re-assigned below to match reality.

### T011 — User Stories planning agent (US1, MVP)

- [x] `api/features/user_stories/planning_agent/user_story_planning_nodes.py` (2 call sites @ lines 68, 315)

### T012 — Requirements → user stories ingestion (US1, MVP)

- [x] `api/features/ingestion/requirements_to_user_stories.py` (2 call sites @ lines 190, 546)

### T019 — Change management planning agent (US3)

- [x] `api/features/change_management/planning_agent/change_planner.py` (1 @ line 305)
- [x] `api/features/change_management/planning_agent/scope_analysis.py` (1 @ line 111)
- [x] `api/features/change_management/planning_agent/plan_revision.py` (1 @ line 89)
- [x] `api/features/change_management/planning_agent/impact_propagation_engine.py` (1 @ line 248)
- [x] `api/features/change_management/planning_agent/plan_finalizer.py` (1 @ line 202)

### T020 — Ingestion workflow phases (US3) — 14 files, ~22 call sites

- [x] `api/features/ingestion/workflow/phases/events.py` (1)
- [x] `api/features/ingestion/workflow/phases/events_from_user_stories.py` (1)
- [x] `api/features/ingestion/workflow/phases/aggregates.py` (2)
- [x] `api/features/ingestion/workflow/phases/bounded_contexts.py` (5)
- [x] `api/features/ingestion/workflow/phases/commands.py` (2)
- [x] `api/features/ingestion/workflow/phases/gwt.py` (3)
- [x] `api/features/ingestion/workflow/phases/policies.py` (2)
- [x] `api/features/ingestion/workflow/phases/properties.py` (3)
- [x] `api/features/ingestion/workflow/phases/readmodels.py` (2)
- [x] `api/features/ingestion/workflow/phases/ui_wireframes.py` (2)
- [x] `api/features/ingestion/workflow/phases/ui_flow_edges.py` (1)
- [x] `api/features/ingestion/workflow/phases/feature_grouping.py` (1)
- [x] `api/features/ingestion/workflow/phases/extract_invariants.py` (1)
- [x] `api/features/ingestion/workflow/phases/user_story_sequencing.py` (2)
- [x] `api/features/ingestion/workflow/phases/link_command_to_events.py` (1)

### T021 — Ingestion event_storming nodes (US3) — 8 files

- [x] `api/features/ingestion/event_storming/nodes_aggregates.py` (1)
- [x] `api/features/ingestion/event_storming/nodes_bounded_contexts.py` (1)
- [x] `api/features/ingestion/event_storming/nodes_breakdown.py` (1)
- [x] `api/features/ingestion/event_storming/nodes_commands.py` (1)
- [x] `api/features/ingestion/event_storming/nodes_events.py` (1)
- [x] `api/features/ingestion/event_storming/nodes_gwt.py` (1)
- [x] `api/features/ingestion/event_storming/nodes_init.py` (1)
- [x] `api/features/ingestion/event_storming/nodes_policies.py` (1)

### T021 (continued) — Ingestion hybrid layer (US3) — 11 files

- [x] `api/features/ingestion/hybrid/bpm_to_user_stories.py` (1)
- [x] `api/features/ingestion/hybrid/document_to_bpm/entity_extractor.py` (2)
- [x] `api/features/ingestion/hybrid/event_storming_bridge/naming.py` (7 call sites — all the displayName generators per ES element type)
- [x] `api/features/ingestion/hybrid/event_storming_bridge/promote_to_es.py` (1)
- [x] `api/features/ingestion/hybrid/mapper/agent_validator.py` (1)
- [x] `api/features/ingestion/hybrid/mapper/condition_extractor.py` (1)
- [x] `api/features/ingestion/hybrid/mapper/cross_process_arbitrator.py` (1)
- [x] `api/features/ingestion/hybrid/mapper/glossary_extractor.py` (1)

### T021 (continued) — Other feature areas (US3) — additional files not in original plan.md estimate

- [x] `api/features/ai_design/openai_translator.py` (1)
- [x] `api/features/ai_design/wireframe_agent.py` (1)
- [x] `api/features/canvas_graph/routes/canvas_expansion.py` (1)
- [x] `api/features/canvas_graph/routes/gwt.py` (1)
- [x] `api/features/figma_binding/component_vlm.py` (1)
- [x] `api/features/ingestion/figma_to_user_stories.py` (1)
- [x] `api/features/model_modifier/react_streaming.py` (3)
- [x] `api/features/model_modifier/routes/ui_wireframe_from_image.py` (1)
- [x] `api/features/prd_generation/html_templates/llm_sections.py` (1)
- [x] `api/features/requirements/clarification_agent/answer_encoder.py` (1)
- [x] `api/features/requirements/feature_grouping_llm.py` (1)

### T022 — Final sweep

- [x] Re-run `grep -rn "SystemMessage(content" api/features/` after all the above are done. Must return ZERO matches. If matches remain, refactor and re-grep until clean.
- [x] Re-run `grep -rln "from langchain_core.messages.*SystemMessage" api/features/` — every remaining import of `SystemMessage` should be removed (no longer needed once `build_system_message` is used everywhere).

---

## T002 — Frontend HTTP client surface audit

**Finding**: There is NO shared HTTP client. The codebase uses raw `window.fetch()` directly inside feature-local `*.api.js` modules and inline in Vue `<script setup>` blocks. Examples:
- `frontend/src/features/invariants/invariants.api.js` — pattern: `fetch('/api/...').then(unwrap)`
- `frontend/src/features/figmaBinding/api.js`
- `frontend/src/features/claudeCode/workspace.api.js`
- `frontend/src/features/requirements/requirements.store.js`
- Inline `fetch` in many `*.vue` components
- `package.json` does NOT include `axios` as a dependency.

**Decision (deviation from contract C3)**: instead of adding an Axios interceptor (no Axios) or migrating ~50 callers to a new shared `apiFetch()` helper (large scope, defeats "single chokepoint"), **patch `window.fetch` globally at app bootstrap**. This is the frontend equivalent of the backend's middleware-at-the-boundary approach: one chokepoint, every caller inherits, zero per-caller migration, zero risk of leaks.

The patched wrapper:
1. Reads `useLanguageStore().language` (already initialized by T010).
2. Merges an `Accept-Language: <tag>` header into the outbound request's headers, preserving any pre-existing `Accept-Language` (so a caller who explicitly sets one wins).
3. Defers to the original `window.fetch` and returns its Promise unchanged.

Lives in [`frontend/src/app/httpInterceptor.js`](../../../frontend/src/app/httpInterceptor.js) (T009), called once from [`frontend/src/main.js`](../../../frontend/src/main.js) bootstrap (T010) immediately after Pinia is registered and the language store is initialized.

**Update to plan/contract**: replace any "Axios interceptor" wording in [`./contracts/language-policy-contract.md`](./contracts/language-policy-contract.md) §C3 with "global `window.fetch` patch at bootstrap." Same chokepoint guarantee, different mechanism. The contract document is the authoritative description; this audit notes the deviation, but the contract itself should be updated as part of T009.

---

## T003 — `desktop/` LLM-call audit

**Finding**: VERIFIED — `desktop/` contains no `SystemMessage`, no `llm.invoke`, no `chat.invoke`. The Electron shell is a Node-side process orchestrator (lifecycle, IPC, settings, auto-update); it spawns the Python backend as a child but does not itself construct LLM prompts. Inherits the language policy transparently because the SPA it hosts is the same SPA the web deployment serves — both pick up the `window.fetch` patch (T002/T009).

```
$ grep -rln "SystemMessage\|llm.invoke\|chat.invoke" desktop/ → no matches
```

No changes to `desktop/` required for feature 031.

---

## Notes for future maintainers

- The 49-file scope (vs. plan's 20-file estimate) is the realistic blast radius. The mechanical refactor takes longer than plan.md projected — budget accordingly.
- The `naming.py` file under `event_storming_bridge` has 7 call sites in one file (per-ES-element-type displayName generators). Refactor in one pass; do not split.
- Test files (`api/features/*/tests/`) intentionally NOT in scope. The AST regression test (T023) excludes tests from its scan. If a test directly constructs `SystemMessage` to assert on the message structure, that's a legitimate test pattern; the regression test only fires for `api/features/` production code.
- Files that import `SystemMessage` but never call it directly (transitive imports) need their import lines cleaned up after the refactor — `from langchain_core.messages import HumanMessage` becomes the only line; `SystemMessage` is dropped.
