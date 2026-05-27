# Implementation Plan: Generation Output Language Policy

**Branch**: `031-generation-language-policy` | **Date**: 2026-05-28 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from [`./spec.md`](./spec.md)

## Summary

All LLM-generated natural-language artifacts in the product (user stories, acceptance criteria, ingestion-workflow event/aggregate/command/UI-wireframe descriptions, change-management plan narratives, DDD spec prose, requirements clarification) must be produced in a language the user selects from the gear-icon Settings panel, defaulting to the browser locale (`navigator.language`, BCP-47).

Technical approach (resolved in research.md): (a) Pinia store + localStorage on the frontend mirroring [theme.store.js](../../../../frontend/src/app/theme.store.js); (b) global Axios interceptor attaches `Accept-Language` to every outbound request; (c) a FastAPI middleware reads `Accept-Language` once per request and writes a `ContextVar` (pattern reused from [request_logging.py](../../../../api/platform/observability/request_logging.py)); (d) **a single shared `SystemMessage` builder in `api/platform/llm_messages.py`** appends a "Respond in {BCP-47 tag}" directive — every existing call site (74 occurrences of `SystemMessage(content=...)` audited) is refactored to call this builder, and an AST-based regression test fails the build if any new direct `SystemMessage(content=...)` is added in `api/features/`.

## Technical Context

**Language/Version**: Python 3.11+ (backend, per Constitution), TypeScript-ish JavaScript ES2022 (frontend Vue 3 + Vite).

**Primary Dependencies**:
- Backend: FastAPI, LangChain (`langchain_core.messages.SystemMessage`), LangGraph, the existing `api.platform.llm.get_llm()` factory (Constitution Principle VI), the existing `api.platform.observability.request_logging` ContextVar pattern.
- Frontend: Vue 3, Pinia (existing in [theme.store.js](../../../../frontend/src/app/theme.store.js) and [terminology.store](../../../../frontend/src/features/terminology/terminology.store.js)), Axios/fetch (verify which HTTP client is the shared layer during T002).

**Storage**: None new. Per-user selection lives in browser `localStorage` (client). Per-request language lives in a Python `ContextVar` (in-memory, request-scoped). No Neo4j changes, no new Pydantic persisted models. (FR-014 in spec.)

**Testing**:
- Backend: `pytest` — unit test for `language.py` helper, integration test for middleware setting the contextvar, AST regression test scanning `api/features/` for unauthorized `SystemMessage(content=...)`.
- Frontend: Existing Vitest/Playwright setup (check `frontend/tests/` for the convention). Unit test for the new Pinia language store. E2E test driving `/api/userstory/plan` end-to-end with three different `Accept-Language` values and asserting on the response text language (via a deterministic LLM-stub or by output-string heuristic).

**Target Platform**: Linux server (FastAPI) + modern evergreen browsers (Vue SPA). Also runs inside the Electron desktop shell (active feature 023, currently paused) — the SPA hosted there inherits the same `navigator.language` path; no shell-side changes needed for this feature.

**Project Type**: Web application (existing `api/` + `frontend/`, plus `desktop/` shell). The split applies cleanly to this feature: a small frontend change (Settings UI + Axios interceptor + Pinia store) and a small platform-level backend change (middleware + ContextVar + shared SystemMessage builder) plus a mechanical refactor of ~74 `SystemMessage` call sites across `api/features/`.

**Performance Goals**:
- Per-request middleware overhead < 1 ms (just header read + ContextVar set + 1 log field).
- Per-LLM-call overhead negligible (the language directive is a constant ≤ 60-char string appended once per system message; token budget impact ≤ 20 tokens per call, dwarfed by typical prompts of thousands of tokens).
- No change to existing throughput or LLM call latency targets.

**Constraints**:
- MUST NOT break existing API contracts (FR-013): only adds a request header at the HTTP boundary, no request-body shape changes, no query-parameter additions.
- MUST NOT change the Neo4j schema (FR-014).
- MUST NOT alter previously stored artifacts (SC-007): no retranslation of existing user stories / events / aggregates.
- MUST stay orthogonal to the existing "Domain Terminology" (`displayName` preference) toggle (FR-012).
- MUST be a single chokepoint (FR-008): zero per-endpoint language-handling code in new generation features added after this ships.

**Scale/Scope**:
- 74 existing `SystemMessage(content=...)` call sites across 20+ files in `api/features/` (audited via `grep -rn "SystemMessage(content" api/`) — all refactored to the new shared builder. Touched files include: `change_management/planning_agent/*` (5 files), `ingestion/requirements_to_user_stories.py`, `ingestion/workflow/phases/*` (12 files: events, aggregates, bounded_contexts, properties, gwt, policies, readmodels, ui_wireframes, ui_flow_edges, feature_grouping, extract_invariants, user_story_sequencing, events_from_user_stories, link_command_to_events), and the user-story / requirements / ddd_spec generation paths.
- 1 new frontend component change ([SettingsPanel.vue](../../../../frontend/src/app/layout/SettingsPanel.vue) + new language store) + 1 HTTP-client interceptor.
- ~4 new backend modules: `api/platform/language.py`, `api/platform/llm_messages.py`, `api/platform/middleware/language_middleware.py` (or fold into an existing middleware), and the regression test.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Evaluated against [constitution.md v1.1.0](../../../../.specify/memory/constitution.md):

| Principle | Status | Notes |
|---|---|---|
| **I. Graph-as-Source-of-Truth** | ✅ PASS | No new persisted state on the graph. Language is per-request ContextVar + client localStorage. FR-014 explicit. |
| **II. Event Storming as Domain Vocabulary** | ✅ PASS | Feature does not introduce or alter domain vocabulary. Acts on the language of generated *text*, not the names of nodes/edges. Orthogonal. |
| **III. Streaming-First UX for Long-Running Work** | ✅ PASS | Pre-existing SSE/WebSocket channels unchanged. Language directive injected into the prompt before LLM call; streamed chunks emerge in the chosen language naturally. |
| **IV. Human-in-the-Loop on Mutations** | ✅ PASS | No new mutation surface. Language change is a per-user UI preference; existing propose→apply flows for graph mutations are unaffected. |
| **V. Feature-Modular Architecture** | ✅ PASS | New code lives in `api/platform/` (cross-cutting, by design). Per-feature touches are restricted to the one-line `SystemMessage(content=...)` → `build_system_message(...)` swap — no new cross-feature imports. |
| **VI. Provider-Agnostic LLM Runtime** | ✅ PASS — and strengthened | The shared SystemMessage builder is provider-agnostic (works for ChatOpenAI / ChatAnthropic / ChatGoogle — they all accept LangChain `SystemMessage`). Language is injected at the LangChain message layer, not at provider SDK level. Aligns with the existing `api/platform/llm.py::get_llm()` boundary. |
| **VII. Observable by Default** | ✅ PASS — and improved | The language middleware emits the resolved language as a structured log field on every request entry (alongside `request_id`). Per-LLM-call logging in `user_story_planning_nodes.py` etc. already includes `params={}` — language will appear there too via the shared builder. Correlation-ID flow preserved. |
| **VIII. Figma SceneGraph Generation Pipeline** | ✅ PASS — N/A | Feature does not touch the open-pencil JSX → Yoga pipeline. SceneGraph emission is not natural-language generation. |
| **IX. Plugin ↔ Backend Dev-Loop Discipline** | ✅ PASS — N/A | No plugin-side changes. |

**Gate verdict**: PASS with zero unjustified violations. Proceed to Phase 0.

## Project Structure

### Documentation (this feature)

```text
specs/031-generation-language-policy/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/
│   └── language-policy-contract.md   # transport + chokepoint contract
├── checklists/
│   └── requirements.md  # already authored by /speckit-specify
└── tasks.md             # Phase 2 output (/speckit-tasks command — NOT created here)
```

### Source Code (repository root)

This is a Web application (existing layout). Touch points:

```text
backend (api/)
├── platform/
│   ├── language.py                                  # NEW — ContextVar + helpers
│   ├── llm_messages.py                              # NEW — shared SystemMessage builder
│   ├── middleware/
│   │   └── language_middleware.py                   # NEW — reads Accept-Language → ContextVar
│   ├── llm.py                                       # UNCHANGED (Constitution VI boundary)
│   └── observability/request_logging.py             # MINOR — add language field to http_context()
├── features/
│   ├── user_stories/planning_agent/
│   │   └── user_story_planning_nodes.py             # REFACTOR — SystemMessage(...) → build_system_message(...)
│   ├── ingestion/
│   │   ├── requirements_to_user_stories.py          # REFACTOR
│   │   └── workflow/phases/
│   │       ├── events.py                            # REFACTOR
│   │       ├── aggregates.py                        # REFACTOR
│   │       ├── bounded_contexts.py                  # REFACTOR
│   │       ├── policies.py                          # REFACTOR
│   │       ├── gwt.py                               # REFACTOR
│   │       ├── ui_wireframes.py                     # REFACTOR
│   │       ├── ui_flow_edges.py                     # REFACTOR
│   │       ├── readmodels.py                        # REFACTOR
│   │       ├── properties.py                        # REFACTOR
│   │       ├── extract_invariants.py                # REFACTOR
│   │       ├── feature_grouping.py                  # REFACTOR
│   │       ├── user_story_sequencing.py             # REFACTOR
│   │       ├── events_from_user_stories.py          # REFACTOR
│   │       └── link_command_to_events.py            # REFACTOR
│   ├── change_management/planning_agent/
│   │   ├── change_planner.py                        # REFACTOR
│   │   ├── scope_analysis.py                        # REFACTOR
│   │   ├── plan_revision.py                         # REFACTOR
│   │   ├── impact_propagation_engine.py             # REFACTOR
│   │   └── plan_finalizer.py                        # REFACTOR
│   ├── requirements/clarification.py                # REFACTOR (if it builds SystemMessages)
│   └── ddd_spec/ ...                                # REFACTOR (audit during T002)
└── main.py                                          # MINOR — register language middleware
└── tests/regression/
    └── test_language_chokepoint.py                  # NEW — AST scan: no unauthorized SystemMessage

frontend (frontend/)
└── src/
    ├── app/
    │   ├── language.store.js                        # NEW — Pinia store + localStorage (mirrors theme.store.js)
    │   └── layout/SettingsPanel.vue                 # MODIFY — add Language section
    ├── services/
    │   └── httpClient.js                            # MODIFY (or NEW if no shared client yet) — Axios interceptor
    └── tests/
        └── unit/language.store.spec.js              # NEW — unit test for store
        └── e2e/                                     # NEW — Playwright test driving 3 locales

desktop (desktop/)                                   # UNCHANGED — SPA hosted by Electron shell inherits browser-locale path
```

**Structure Decision**: Web-application structure (Option 2 in template). The change is intentionally weighted toward `api/platform/` (one chokepoint serving all features) rather than per-feature changes. Per-feature files appear in the refactor list only to flip one symbol (`SystemMessage` → `build_system_message`), making US3's "single architectural touchpoint" success criterion concrete: after this PR, a developer adding a new generation feature touches zero language-policy files.

## Complexity Tracking

> No constitution violations to justify. Section retained as a placeholder per template; no entries needed.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |
