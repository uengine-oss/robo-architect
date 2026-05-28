<!-- SPECKIT START -->
Active feature plan: [specs/031-generation-language-policy/plan.md](specs/031-generation-language-policy/plan.md)

Read the plan for technologies, project structure, constitution gates, and architectural constraints relevant to current work. Companion artifacts in the same directory:
- spec.md (what & why — Every LLM-generated natural-language artifact in the product — user stories, acceptance criteria, ingestion-workflow event/aggregate/command/UI-wireframe descriptions, change-management plan narratives, DDD spec prose, requirements clarification — must be produced in a language the user selects from the gear-icon Settings panel. Default = `navigator.language` (BCP-47). UI i18n out of scope. Existing stored artifacts not retranslated. No Neo4j schema change, no new Pydantic models, no new request-body fields — single `Accept-Language` header at the HTTP boundary.)
- research.md (D1 `Accept-Language` standard header set globally; D2 server-side fallback = **`en-US`** + `GENERATION_LANGUAGE_DEFAULT` env override; D3 single shared `build_system_message()` in `api/platform/llm_messages.py`; D4 per-request `ContextVar` in `api/platform/language.py`; D5 AST-based pytest regression at `api/tests/regression/test_language_chokepoint.py`; D6 one-PR refactor; D7 Pinia store mirrors `theme.store.js`; D8 user-supplied input verbatim preserved.)
- data-model.md (No Neo4j schema change, no new Pydantic models. Effective Language client-side / Language Context server-side ContextVar / Generated Output via chokepoint.)
- contracts/language-policy-contract.md (C1 `Accept-Language` header / C2 backend `build_system_message` chokepoint / C3 frontend `useLanguageStore` + **global `window.fetch` patch** at bootstrap — deviation from original axios design recorded in refactor-audit.md, codebase has no axios dep.)
- refactor-audit.md (Actual scope: **70 SystemMessage call sites × 46 files** in api/features/ — wider than plan's 20-file estimate. Per-file checklist, all [x] after implement pass.)
- quickstart.md (9 manual smoke scenarios.)
- mvp-validation.md (Per-task implementation status after /speckit-implement: 22 codable tasks [x], 10 manual browser/curl smokes ⏸ deferred with rationale, automated-test totals **973 PASS** with zero new failures.)

**Phase progress (this branch, started 2026-05-28):**
- /speckit-specify ✅ — spec.md + checklists/requirements.md
- /speckit-plan ✅ — plan.md + research.md + data-model.md + contracts/ + quickstart.md
- /speckit-tasks ✅ — tasks.md with 34 work items, US1=MVP cut
- /speckit-implement ✅ (codable portion) — Phase 1+2+3+4+5+6 implemented in one pass:
  - Phase 1 audit + Phase 2 platform plumbing (`api/platform/{language,llm_messages,middleware/language_middleware}.py` + 43 unit tests + `frontend/src/app/{language.store,httpInterceptor}.js` + `main.js` bootstrap + `api/main.py` middleware wiring + `http_context()` language field)
  - Phase 3 US1 refactors (`user_story_planning_nodes` + `requirements_to_user_stories`)
  - Phase 4 US2 UI (SettingsPanel.vue Language section + datalist + validation in store)
  - Phase 5 US3 mass mechanical refactor (70 calls / 46 files; final sweep zero remaining) + AST regression test (660 parametric cases + meta-detector PASS)
  - Phase 6 polish (.env.example + README API note + contract C3 deviation update)
- Manual smoke ⏸ — quickstart.md S1/S2/S3/S5/S6/S7/S8/S9 require running stack (uvicorn + npm run dev). See mvp-validation.md.
<!-- SPECKIT END -->
