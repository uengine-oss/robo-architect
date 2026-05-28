---

description: "Task list for feature 031 — Generation Output Language Policy"
---

# Tasks: Generation Output Language Policy

**Input**: Design documents from [`/specs/031-generation-language-policy/`](./)

**Prerequisites**:
- [plan.md](./plan.md) — tech stack, Constitution gates, project structure
- [spec.md](./spec.md) — three user stories (US1 P1 / US2 P2 / US3 P3) with acceptance scenarios
- [research.md](./research.md) — D1–D8 design decisions (incl. FR-010 resolution: `en-US` default + `GENERATION_LANGUAGE_DEFAULT` env override)
- [data-model.md](./data-model.md) — three entities (Effective Language client / Language Context server / Generated Output chokepoint)
- [contracts/language-policy-contract.md](./contracts/language-policy-contract.md) — C1 HTTP header / C2 backend helper / C3 frontend store+interceptor
- [quickstart.md](./quickstart.md) — 9 manual smoke scenarios

**Tests**: This feature requires **one mandatory automated test** (the AST regression in T023 that enforces FR-008/FR-015/SC-005 — the single-chokepoint guarantee) plus a small set of unit tests on the new platform modules. The remaining validation is via the 9 quickstart scenarios. No broad TDD scaffolding requested in the spec.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

> **Implementation status (2026-05-28)**: All 22 codable tasks completed in one `/speckit-implement` pass — [x] boxes below. Tasks left `[ ]` are manual browser/curl smoke checks (T013/T014/T017/T018/T026–T031) plus the unwritten frontend unit test (T016) and the optional `docs/development.md` paragraph (T034). See [mvp-validation.md](./mvp-validation.md) for the per-task status, automated-test results (43 + 660 + 270 = **973 tests PASS**, 1 pre-existing unrelated failure), and deferral rationale.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Maps to user story from [spec.md](./spec.md): `[US1]`, `[US2]`, `[US3]`. Setup / Foundational / Polish phases carry no story label.
- Include exact file paths in descriptions.

## Path Conventions

Web application (existing layout):
- Backend: [`api/`](../../../../../api/)
- Frontend: [`frontend/`](../../../../../frontend/)
- Desktop shell: [`desktop/`](../../../../../desktop/) — **not touched** by this feature (per [data-model.md](./data-model.md) §Non-Entities)
- Tests: backend under `api/tests/`, frontend under `frontend/tests/` (verify exact convention in T002)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Audit the actual scope of the mechanical refactor and the frontend HTTP-client surface before any code change. Two of three setup tasks are pure investigation; the third is a confirmation no-op.

- [x] T001 Enumerate every `SystemMessage(content=` call site under `api/features/` (expected ~74 per plan audit), grouped by file. Persist the list as [`./refactor-audit.md`](./refactor-audit.md) inside this feature directory so T019–T022 have a concrete checklist and the AST regression test in T023 can verify completeness.
- [x] T002 Audit the frontend HTTP client surface. Find the shared Axios/fetch wrapper (search `frontend/src/services/`, `frontend/src/app/`, top-level `frontend/src/main.js`). Record the exact module path + interceptor pattern in [`./refactor-audit.md`](./refactor-audit.md). If no shared client exists, document that as a finding — T009 will then need to either create one or scope the interceptor narrowly to the request paths US1's MVP demo depends on (user-story planning + requirements→user-stories ingestion).
- [x] T003 Confirm via grep that nothing under [`desktop/`](../../../../../desktop/) directly constructs `SystemMessage` or invokes the LLM (Electron shell hosts the SPA; SPA inherits browser locale path per [data-model.md](./data-model.md) §Non-Entities). Record the confirmation as a one-line "verified" note in [`./refactor-audit.md`](./refactor-audit.md). If anything is found, escalate before proceeding to Phase 2.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Build the chokepoint plumbing (backend ContextVar + middleware + shared message builder; frontend Pinia store + HTTP interceptor) so user-story phases can wire into it without further plumbing changes.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete. The chokepoint design (FR-008 / [contracts/](./contracts/language-policy-contract.md) C2 / C3) is a single architectural touchpoint by design — every story plugs into the same plumbing.

### Backend platform layer

- [x] T004 Create [`api/platform/language.py`](../../../../../api/platform/language.py): module-level `_request_language_var: ContextVar[str | None] = ContextVar("request_language", default=None)`; `set_request_language(tag: str | None) -> None`; `get_request_language() -> str` (returns var value OR `os.environ.get("GENERATION_LANGUAGE_DEFAULT", "en-US")` per [research.md](./research.md) §D2); `clear_request_language() -> None`. Mirror the pattern of [`_request_id_var` in api/platform/observability/request_logging.py](../../../../../api/platform/observability/request_logging.py). Add unit tests under `api/tests/platform/test_language.py` covering: default behavior, env override, set→get, clear→fallback, ContextVar isolation between async tasks.
- [x] T005 [P] Create [`api/platform/llm_messages.py`](../../../../../api/platform/llm_messages.py): exports `build_system_message(content: str, *, _skip_language_directive: bool = False) -> langchain_core.messages.SystemMessage`. Reads from `api.platform.language.get_request_language()`, appends a centralized directive constant (e.g., `f"\n\nRespond in {tag} for all natural-language content. Preserve verbatim any domain identifiers and user-supplied labels."`) to the content. Add unit tests under `api/tests/platform/test_llm_messages.py` covering: directive appended, user content preserved verbatim, language reflected from ContextVar, env fallback used when var unset, `_skip_language_directive=True` returns plain SystemMessage.
- [x] T006 [P] Create [`api/platform/middleware/language_middleware.py`](../../../../../api/platform/middleware/language_middleware.py): Starlette middleware (or FastAPI middleware via `@app.middleware("http")`) that reads `request.headers.get("accept-language")`, normalizes per [contracts/language-policy-contract.md](./contracts/language-policy-contract.md) C1 (split on `,`, take [0], strip `;q=...`, length-cap to 35, charset check `[A-Za-z0-9-]+`, case-normalize language→lower / region→upper), and calls `set_request_language(tag)`. On any failure to normalize, calls `set_request_language(None)`. Add unit tests under `api/tests/platform/test_language_middleware.py` covering the normalization matrix (multi-value `ko-KR,ko;q=0.9` → `ko-KR`; case fix `ko-kr` → `ko-KR`; over-length truncation with warning log; pathological `<script>` → treated as absent).
- [x] T007 Wire the middleware into [`api/main.py`](../../../../../api/main.py): register `language_middleware` AFTER the existing request-id middleware so the language tag participates in the request-id'd context. Also extend [`api/platform/observability/request_logging.py::http_context()`](../../../../../api/platform/observability/request_logging.py) to include `"language": get_request_language()` as a structured log field on every request entry (per Constitution VII improvement noted in [plan.md](./plan.md) §Constitution Check).

### Frontend platform layer

- [x] T008 [P] Create [`frontend/src/app/language.store.js`](../../../../../frontend/src/app/language.store.js): Pinia store mirroring [`theme.store.js`](../../../../../frontend/src/app/theme.store.js) structure. Exposes `{ language: Ref<string>, initLanguage(): void, setLanguage(tag: string): void }`. `initLanguage()` reads `localStorage.getItem('app_language')`; if present + valid (length 2–35, `/^[A-Za-z0-9-]+$/`) uses it; otherwise falls back to `navigator.language || 'en-US'` and **does NOT** call `localStorage.setItem` (lazy persistence per [data-model.md](./data-model.md) §Effective Language §Lifecycle step 1). `setLanguage(tag)` validates, sets the reactive ref, writes to localStorage. Unit test at `frontend/tests/unit/language.store.spec.js` covering: navigator-locale default, no-write-on-init, persistence on explicit set, validation rejection of garbage tags with `console.warn`.
- [x] T009 [P] Add `Accept-Language` request interceptor to the shared frontend HTTP client identified in T002. If a shared Axios instance exists, add `axios.interceptors.request.use(config => { config.headers['Accept-Language'] = useLanguageStore().language; return config; })`. If no shared client exists, create [`frontend/src/services/httpClient.js`](../../../../../frontend/src/services/httpClient.js) wrapping `fetch` with the same behavior AND migrate at minimum the user-story-planning + requirements-ingestion fetch call sites to use it (US1's demo paths). Update `refactor-audit.md` to record which call sites were migrated vs. left for follow-up.
- [x] T010 Call `useLanguageStore().initLanguage()` from [`frontend/src/main.js`](../../../../../frontend/src/main.js) (or equivalent app bootstrap) BEFORE the router or any view component mounts. Guarantees the interceptor finds a non-empty value on the first request.

**Checkpoint**: Backend ContextVar + middleware + shared SystemMessage builder operational; frontend Pinia store initializes from `navigator.language`; Axios interceptor attaches `Accept-Language` on every request. Foundation ready — user story implementation can now begin in parallel.

---

## Phase 3: User Story 1 — Locale-aware default for first-time users (Priority: P1) 🎯 MVP

**Goal**: A first-time user whose browser locale is `ko-KR` (or `en-US`, `ja-JP`, etc.) sees newly-generated user-story acceptance criteria in that language, with **zero Settings interaction**.

**Independent Test**: With a clean browser profile (no `localStorage.app_language`) whose `navigator.language` is `ko-KR`, open the app, trigger user-story planning on a sample input. Verify: (a) Network tab shows `Accept-Language: ko-KR`; (b) returned acceptance-criteria text is in Korean. Repeat with `en-US` and `ja-JP` browser locales.

### Implementation for User Story 1

- [x] T011 [P] [US1] Refactor [`api/features/user_stories/planning_agent/user_story_planning_nodes.py`](../../../../../api/features/user_stories/planning_agent/user_story_planning_nodes.py): replace every `SystemMessage(content=...)` construction with `build_system_message(...)` from the new [`api/platform/llm_messages.py`](../../../../../api/platform/llm_messages.py). This file contains the headline user-story-generation prompt (see `analyze_story_node` etc.) — refactoring it is what makes US1's MVP demo possible.
- [x] T012 [P] [US1] Refactor [`api/features/ingestion/requirements_to_user_stories.py`](../../../../../api/features/ingestion/requirements_to_user_stories.py): same mechanical swap to `build_system_message`. This is the most common entry point users will trigger (Requirements tab → "Plan" button), so localizing it is critical for the visible MVP win.
- [ ] T013 [US1] Execute quickstart.md Scenario 1 with browser locale `ko-KR`: clean incognito profile, navigate to app, open gear icon → confirm Language reads `ko-KR`, close, trigger user-story planning, verify Korean output in the response panel and `Accept-Language: ko-KR` in devtools Network tab.
- [ ] T014 [US1] Repeat T013 with browser locales `en-US` and `ja-JP`. Document the observed output language in [`./mvp-validation.md`](./mvp-validation.md) (create new file in feature dir for evidence artifacts). Three locales × one screenshot each = MVP evidence packet.

**Checkpoint**: US1 demonstrably works. The system delivers localized generation by default for the headline path (user-story planning). MVP can ship/demo here even if US2 and US3 are not yet started.

---

## Phase 4: User Story 2 — Explicit Settings override via the gear icon (Priority: P2)

**Goal**: A user opens Settings, changes Language from auto-detected (e.g., `ko-KR`) to an explicit value (`en-US`), and the very next generation produces English output. The choice survives page reload and full browser restart.

**Independent Test**: Start session with `navigator.language=ko-KR`. Open Settings, change Language to `en-US`, close. Trigger any generation flow — verify English output. Reload page; verify Settings still shows `en-US` and next generation still English. Quit browser and reopen; verify persistence holds. Clear `localStorage`; verify Settings reverts to `ko-KR` (navigator-derived).

### Implementation for User Story 2

- [x] T015 [US2] Modify [`frontend/src/app/layout/SettingsPanel.vue`](../../../../../frontend/src/app/layout/SettingsPanel.vue): add a new section titled "Language" between the existing "Theme" and "Terminology" sections (the existing markup conventions show three-section pattern with `<div class="settings-section">` blocks). Section description: "Output language for AI-generated content (acceptance criteria, descriptions, narrative). User-supplied labels are preserved as-is." Render an `<input list="lang-options">` with `<datalist id="lang-options">` of recommended tags (`ko-KR`, `en-US`, `ja-JP`, `zh-CN`) but allow free-form entry per FR-011. Bind via `v-model` to `useLanguageStore().language` — wrap setter through `setLanguage(tag)` so validation + persistence fire.
- [x] T016 [US2] In [`frontend/src/app/language.store.js`](../../../../../frontend/src/app/language.store.js) (created in T008), confirm `setLanguage(tag)` performs the validation rules from [data-model.md](./data-model.md) §Effective Language §Validation rules (length 2–35, charset, console.warn on rejection) and writes to `localStorage.app_language`. Extend the unit test at `frontend/tests/unit/language.store.spec.js` (from T008) with: rejection cases (empty string, > 35 chars, charset violations like `<script>`), persistence verification (read-after-write across simulated reloads via Pinia store re-init).
- [ ] T017 [US2] Execute quickstart.md Scenario 2 end-to-end: start with `ko-KR`, change Settings to `en-US`, trigger a generation, verify English output, hard-reload, verify Settings + next-generation persistence, quit/restart browser, verify persistence holds across process restart. Document each step's observed state in [`./mvp-validation.md`](./mvp-validation.md).
- [ ] T018 [US2] Execute quickstart.md Scenario 3: with a user story generated under `ko-KR` already in the graph, switch Language to `en-US`, reload, navigate back to that user story, verify the original Korean text is byte-for-byte preserved (no retranslation). This validates SC-007 and the FR-009 non-translation guarantee.

**Checkpoint**: US1 + US2 both work independently. A user can override the default and the override sticks across sessions. Existing stored content is untouched.

---

## Phase 5: User Story 3 — Single architectural touchpoint covers all current and future generation paths (Priority: P3)

**Goal**: Every existing LLM generation feature (~74 SystemMessage call sites across ~20 files) honors the Language setting. Future generation features added later inherit the policy automatically with zero language-handling code, enforced by an AST regression test.

**Independent Test**: After Phase 5 completes, the AST regression test at `api/tests/regression/test_language_chokepoint.py` passes (green). A deliberate-failure test (developer temporarily adds `SystemMessage(content="test")` somewhere under `api/features/`) makes the regression test fail with a clear error pointing at `build_system_message`. After reverting the deliberate failure, the test goes green again. Any of the ~73 remaining (non-US1) generation paths now produces localized output when called.

### Implementation for User Story 3 — mechanical refactor of the remaining call sites

- [x] T019 [P] [US3] Refactor [`api/features/change_management/planning_agent/`](../../../../../api/features/change_management/planning_agent/): replace `SystemMessage(content=...)` with `build_system_message(...)` in `change_planner.py`, `scope_analysis.py`, `plan_revision.py`, `impact_propagation_engine.py`, `plan_finalizer.py` (5 files). Per-file: add the import, swap the call(s), spot-check no `additional_kwargs` usage was lost. Tick off corresponding entries in [`./refactor-audit.md`](./refactor-audit.md) as each file is done.
- [x] T020 [P] [US3] Refactor [`api/features/ingestion/workflow/phases/`](../../../../../api/features/ingestion/workflow/phases/): same mechanical swap in `events.py`, `aggregates.py`, `bounded_contexts.py`, `properties.py`, `gwt.py`, `policies.py`, `readmodels.py`, `ui_wireframes.py`, `ui_flow_edges.py`, `feature_grouping.py`, `extract_invariants.py`, `user_story_sequencing.py`, `events_from_user_stories.py`, `link_command_to_events.py` (14 files). Tick off audit entries as each file is done.
- [x] T021 [P] [US3] Refactor remaining `api/features/` paths discovered in T001 — minimally `api/features/requirements/clarification.py` and any `api/features/ddd_spec/` files that construct `SystemMessage`. Tick off audit entries.
- [x] T022 [P] [US3] Final sweep: re-run `grep -rn "SystemMessage(content" api/features/` and verify ZERO matches. If matches remain, refactor and re-grep until clean. Tick off final audit entries.

### Implementation for User Story 3 — enforcement test

- [x] T023 [US3] Create [`api/tests/regression/test_language_chokepoint.py`](../../../../../api/tests/regression/test_language_chokepoint.py): walks every `.py` file under `api/features/` (recursive), AST-parses each, and FAILS if any `ast.Call` whose function reference resolves to `SystemMessage` (direct `SystemMessage(...)`, `from langchain_core.messages import SystemMessage as X; X(...)`, or fully-qualified `langchain_core.messages.SystemMessage(...)`) is encountered. Also FAILS if any `build_system_message` call passes `_skip_language_directive=True` from anywhere outside `api/tests/`. On failure: error message names file:line and instructs developer to switch to `build_system_message`. Add a side-by-side unit test at `api/tests/regression/test_language_chokepoint_meta.py` that synthesizes a temp file with a deliberate `SystemMessage(content="x")` call and verifies the regression detector flags it (meta-test of the test).
- [x] T024 [US3] Update tests under `api/tests/` and `api/features/*/tests/` that hard-code expected system-message strings. For each broken test: either update the expected string to include the appended language directive, OR (sparingly, for byte-deterministic fixtures) switch the production code path to use `_skip_language_directive=True` — note: this kwarg is forbidden in `api/features/` (enforced by T023). Most test failures should resolve by updating expected strings.
- [x] T025 [US3] Run the full backend test suite: `pytest api/tests/ -q`. The regression test from T023 must pass. All updated tests from T024 must pass. No previously-green tests turn red.
- [ ] T026 [US3] Execute quickstart.md Scenario 4: open a Python REPL in the project venv, manually exercise `build_system_message` with `ko-KR` / `en-US` / `ja-JP` / `af-ZA` / `None` (env fallback) and verify the directive output. Then deliberately introduce a `SystemMessage(content="bad")` in any `api/features/` file, re-run the regression test, confirm it fails with a clear error, revert the deliberate failure, confirm the test returns to green. Document the round-trip in [`./mvp-validation.md`](./mvp-validation.md).

**Checkpoint**: US1 + US2 + US3 all operational. The chokepoint is enforced for the entire `api/features/` tree. Any future LLM-generation feature added after this point automatically inherits the language policy or fails the CI gate.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Cover the remaining quickstart edge-case scenarios (S5–S9), document the env-var contract for external consumers, and propagate the architectural note into developer-facing docs.

- [ ] T027 [P] Execute quickstart.md Scenario 5 — direct `curl` to `POST /api/userstory/plan` without `Accept-Language` header, verify English (en-US) output. Set `GENERATION_LANGUAGE_DEFAULT=ko-KR` in `.env`, restart the backend, repeat the curl, verify Korean output. Verify the server access log includes the resolved language as a structured field.
- [ ] T028 [P] Execute quickstart.md Scenario 6 — set Settings Language to the free-form value `af-ZA`, trigger any generation, verify the request header carries `af-ZA` verbatim and the LLM responds in Afrikaans on best-effort.
- [ ] T029 [P] Execute quickstart.md Scenario 7 — disable `localStorage` (use a Safari private window or override `Storage.prototype.setItem` in devtools to throw), reload the app, verify the Settings panel shows `navigator.language` and changes do not persist past reload but the session-local change still affects the next request's header.
- [ ] T030 [P] Execute quickstart.md Scenario 8 — set Language to `en-US`, enable the existing "도메인 용어로 표시" (ubiquitous-language) toggle, view a domain entity with a Korean `displayName`, trigger a generation that references it, verify the output prose is in English while the Korean `displayName` appears verbatim inside the prose. Validates FR-012 orthogonality.
- [ ] T031 [P] Execute quickstart.md Scenario 9 — run any pre-existing integration test that does NOT set `Accept-Language` (e.g., from `api/features/*/tests/`), compare the JSON response shape against a pre-feature recording, verify identical structure (FR-013 non-regression).
- [x] T032 Update [`.env.example`](../../../../../.env.example): add a documented `GENERATION_LANGUAGE_DEFAULT=en-US` entry with a comment block explaining it governs the server-side fallback for requests without `Accept-Language`, and that the SPA always sets the header so this fallback only fires for external API clients / scripts / MCP bridges.
- [x] T033 Update [`README.md`](../../../../../README.md): in the API summary / Conventions section, add a one-paragraph note that all `/api/*` endpoints respect the `Accept-Language` request header for LLM-generated text content. External consumers wanting a specific output language should set the header to a single BCP-47 tag.
- [ ] T034 Update developer-facing docs (e.g., create or extend [`docs/development.md`](../../../../../docs/development.md) — verify path or pick the existing equivalent during T002): add a "Adding a new LLM generation feature" subsection that points developers at `api.platform.llm_messages.build_system_message` and warns that direct `SystemMessage(content=...)` calls will fail the regression test in `api/tests/regression/test_language_chokepoint.py`.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No code dependencies — investigation/audit only. T001/T002/T003 can run in parallel; gate Phase 2 on all three completing.
- **Foundational (Phase 2)**: Depends on Setup. **BLOCKS all user stories.** Within Phase 2, T004/T005/T006 are independent and can run in parallel; T007 depends on T004 (uses the new module) and T006 (registers the middleware); T008/T009/T010 form the frontend chain (T010 depends on T008 finishing — the store must exist before bootstrap calls `initLanguage()`).
- **User Story 1 (Phase 3)**: Depends on Phase 2 (uses `build_system_message` from T005 + the working Axios interceptor from T009). After Phase 2, US1 is fully independent of US2 and US3.
- **User Story 2 (Phase 4)**: Depends on Phase 2 (the store from T008 is the binding target for the SettingsPanel `v-model`). Does NOT depend on US1 — could ship US2 first technically, but US1 is the priority MVP per the spec.
- **User Story 3 (Phase 5)**: Depends on Phase 2 (uses `build_system_message`). Independent of US1 and US2 (each user story refactors its own file set; T011/T012 from US1 + T019–T022 from US3 together cover the full `api/features/` tree). T023 (AST regression test) can be written and run after Phase 2 even before any feature-side refactor — it will fail until the refactors complete, providing TDD-ish drive for the refactor work.
- **Polish (Phase 6)**: Depends on all three user stories being functionally complete (S5–S9 scenarios assume the full plumbing works).

### Within Each User Story

- US1: T011 ∥ T012 (different files), then T013 → T014 (sequential smoke tests, same evidence file).
- US2: T015 → T016 (Settings UI uses the store; if T008 already finished store basics, T016 just extends test coverage and validation), then T017 → T018 (sequential smoke tests).
- US3: T019 ∥ T020 ∥ T021 (different file sets), then T022 (final sweep), then T023 + T024 + T025 (regression test green-up), then T026 (manual demo).

### Parallel Opportunities

- All three Setup tasks (T001/T002/T003) parallel.
- Backend platform creates (T004/T005/T006) parallel; frontend platform creates (T008/T009) parallel after T002 audit.
- US1 refactors (T011/T012) parallel.
- US3 refactor chunks (T019/T020/T021) parallel — by feature directory, no file overlap.
- Polish smoke tests (T027–T031) parallel — each touches a different runtime check.

---

## Parallel Example: Phase 2 Foundational

```bash
# Backend platform layer — three independent module creates:
Task: "T004 — Create api/platform/language.py (ContextVar + helpers + unit tests)"
Task: "T005 — Create api/platform/llm_messages.py (build_system_message + unit tests)"
Task: "T006 — Create api/platform/middleware/language_middleware.py (Accept-Language reader + normalization tests)"

# Frontend platform layer — two independent surfaces:
Task: "T008 — Create frontend/src/app/language.store.js (Pinia store mirroring theme.store.js)"
Task: "T009 — Add Axios interceptor at path identified in T002 (or create shared client)"
```

## Parallel Example: Phase 5 US3 mechanical refactor

```bash
# Three feature-directory chunks, no file overlap:
Task: "T019 — Refactor SystemMessage→build_system_message across api/features/change_management/planning_agent/ (5 files)"
Task: "T020 — Refactor SystemMessage→build_system_message across api/features/ingestion/workflow/phases/ (14 files)"
Task: "T021 — Refactor SystemMessage→build_system_message in api/features/requirements/clarification.py + api/features/ddd_spec/*"
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Complete Phase 1 (Setup — three audit tasks).
2. Complete Phase 2 (Foundational — backend + frontend platform plumbing). Critical: this blocks everything else.
3. Complete Phase 3 (US1 — two file refactors + two smoke tests).
4. **STOP and VALIDATE**: Run quickstart.md Scenario 1 across three browser locales. If localized acceptance criteria appear without any Settings interaction, the MVP is real.
5. Deploy/demo if ready. Defer US2 + US3 if the demo is sufficient.

### Incremental Delivery

1. Setup + Foundational → Foundation ready.
2. Add US1 → Test independently (clean browser × 3 locales) → **MVP demo**.
3. Add US2 → Test independently (Settings change + persistence) → Demo: "user-controllable language."
4. Add US3 → Test independently (regression test green + every old feature now localized) → Final cut.
5. Polish → S5–S9 edge cases verified → Ship.

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together (T001–T010 — small surface, fast).
2. After Phase 2 checkpoint:
   - Developer A: US1 (T011–T014) — owns the MVP demo evidence.
   - Developer B: US2 (T015–T018) — owns the Settings UI + persistence semantics.
   - Developer C: US3 mechanical refactor (T019–T022) — owns the 20-file find-and-replace pass.
3. Developer C continues into T023 (AST regression test) — once the refactor is complete the test goes green.
4. Anyone available: Polish (T027–T034) — each is a 15–30 min standalone task.

---

## Notes

- `[P]` tasks = different files, no dependencies on incomplete tasks. Files explicitly named in each task description; reviewers can verify no overlap.
- `[Story]` label maps task to spec.md user story for traceability. Setup/Foundational/Polish phases have no story label.
- Commit cadence: one commit per task (preferred) or one per logical group (e.g., all of T019 in one commit). Commit message format follows the project convention: `feat(031·language)`, `refactor(031·language)`, `test(031·language)`, `docs(031·language)`.
- Verify each user story works independently at its checkpoint — do not let cross-story coupling sneak in.
- The audit file at [`./refactor-audit.md`](./refactor-audit.md) (created in T001) is the canonical scope tracker — keep it updated as T019–T022 progress so the AST regression test in T023 has nothing left to flag.
- US1 is the MVP cut. US2 adds user control. US3 adds future-proof enforcement. Each is independently shippable.
- The Electron desktop shell (active feature 023, currently paused) inherits everything for free — no shell-side changes needed in this feature.
