# Quickstart: Generation Output Language Policy

**Feature**: 031-generation-language-policy
**Date**: 2026-05-28

Manual smoke scenarios for validating the feature end-to-end. Each scenario is independently runnable. Scenarios 1–4 cover the spec's three user stories (P1 / P2 / P3). Scenarios 5–9 cover edge cases and non-regression guarantees.

**Prerequisites for all scenarios**:
- Backend running locally: `uvicorn api.main:app --reload --host 127.0.0.1 --port 8000` (per Constitution Principle IX).
- Frontend running locally: `cd frontend && npm run dev` (or equivalent for this project's dev workflow).
- Neo4j running and reachable per `.env` (`NEO4J_URI` etc.).
- A clean browser profile per scenario where noted (use an incognito/private window for "fresh session" requirements).

---

## Scenario 1 — Default language follows browser locale (US1, P1)

**Goal**: Verify that a first-time user gets generated output in their browser's language without any Settings interaction.

**Steps**:

1. In your OS or browser, set the active language to Korean (`ko-KR`). On macOS: System Settings → General → Language & Region → primary = Korean.
2. Open a brand-new incognito/private browser window (clean `localStorage`).
3. Navigate to `http://localhost:5173` (or the project's dev port).
4. Open the gear icon in the top bar → Settings panel. Confirm the **Language** field reads `ko-KR`. Do NOT change it. Close the panel.
5. Trigger a user-story generation flow (e.g., navigate to the Requirements tab → enter a sample feature description → click "Plan").
6. Wait for the streaming response to complete.

**Expected**:
- Settings panel's Language field shows `ko-KR` on first open.
- Generated acceptance criteria, summaries, and any LLM-produced descriptions are in Korean.
- The browser's devtools Network tab shows `Accept-Language: ko-KR` on the outgoing request to `/api/...`.

**Repeat** steps 2–6 with the browser locale set to `en-US` and then `ja-JP`. Expected outputs: English and Japanese respectively.

---

## Scenario 2 — Explicit Settings override persists across reloads (US2, P2)

**Goal**: Verify that an explicit language choice in Settings persists across page reloads and browser restarts, and takes effect on the very next generation.

**Steps**:

1. Continue from Scenario 1's final state (or start fresh with browser locale `ko-KR`).
2. Open Settings via the gear icon. Change Language to `en-US`. Close the panel.
3. Trigger any LLM generation flow (user-story plan, requirements clarify, change planning, etc.).
4. Verify output is in English.
5. Hard-refresh the page (`Cmd+Shift+R` / `Ctrl+Shift+R`).
6. Open Settings — verify Language still shows `en-US`.
7. Trigger another generation flow — verify output is still in English.
8. Quit the browser entirely and reopen. Navigate to the app.
9. Open Settings — verify Language still shows `en-US`.

**Expected**:
- Settings change is visible immediately in the UI.
- Next generation produces English output, even though OS locale is Korean.
- The `localStorage.app_language` key (visible in devtools → Application → Local Storage) holds `en-US` after the change.
- Choice survives reload and full browser restart.

---

## Scenario 3 — Previously stored artifacts are untouched (US2 → SC-007)

**Goal**: Verify that switching Language does NOT retroactively translate stored content.

**Steps**:

1. With Language=`ko-KR`, run a user-story generation flow and let it persist (apply the planned user story to the graph).
2. Note the exact Korean text of the acceptance criteria sentences in the resulting node.
3. Open Settings, change Language to `en-US`. Close.
4. Reload the page. Navigate back to the same user story.

**Expected**:
- The previously-saved Korean acceptance criteria sentences are still present, unchanged, byte-for-byte.
- No translation, paraphrase, or normalization has occurred.
- New generations (if you trigger one) produce English text — appended/composed alongside the preserved Korean records.

---

## Scenario 4 — New generation node added later inherits the policy automatically (US3, P3)

**Goal**: Verify the chokepoint design: a hypothetical new LLM-driven feature, wired through `build_system_message`, gets the language policy with zero extra code.

**Steps** (developer / reviewer):

1. Open a Python REPL in the project's virtualenv:
   ```python
   from api.platform.language import set_request_language
   from api.platform.llm_messages import build_system_message

   set_request_language("ja-JP")
   msg = build_system_message("You are a DDD expert analyzing user stories.")
   print(msg.content)
   ```
2. Verify the printed content ends with the language directive instructing the model to respond in `ja-JP`.
3. Repeat with `ko-KR`, `en-US`, and `af-ZA` (unsupported-but-valid BCP-47 tag).
4. Call `set_request_language(None)` and call `build_system_message` again — verify the directive uses the env-default fallback (`en-US` unless `GENERATION_LANGUAGE_DEFAULT` is set).
5. Run the regression test:
   ```bash
   pytest api/tests/regression/test_language_chokepoint.py -v
   ```
6. As a deliberate-failure check, temporarily edit any file under `api/features/` to add `SystemMessage(content="test")`. Re-run the regression test.

**Expected**:
- Step 2: the directive is present and contains `ja-JP`.
- Step 3: directive uses each tag verbatim, including the unsupported `af-ZA` (FR-011).
- Step 4: directive uses the env-default language.
- Step 5: regression test passes (green).
- Step 6: regression test fails, with an error message that names the offending file:line and points at `build_system_message`. (Remember to revert the deliberate failure!)

---

## Scenario 5 — No `Accept-Language` header → server-side default fires (FR-010)

**Goal**: Verify the FR-010 fallback path for external clients that don't speak the SPA's interceptor convention.

**Steps**:

1. With the backend running, send a direct request from `curl`:
   ```bash
   curl -X POST http://127.0.0.1:8000/api/userstory/plan \
     -H "Content-Type: application/json" \
     -d '{"role":"shopper","action":"add a product to cart","benefit":"so I can purchase it"}'
   ```
   (Adjust to a real endpoint signature if needed.)
2. Note: no `Accept-Language` header is sent.
3. Inspect the response — generated acceptance criteria should be in `en-US` (per D2 default).
4. Stop the backend. Set `GENERATION_LANGUAGE_DEFAULT=ko-KR` in `.env`. Restart the backend.
5. Repeat the curl request.

**Expected**:
- Step 3: response is English.
- Step 5: response is Korean.
- Server access logs include the resolved language as a structured field on the request entry.

---

## Scenario 6 — Exotic-but-valid BCP-47 tag passes through (FR-011, edge case)

**Goal**: Verify that an unusual tag is not rejected and is forwarded to the LLM verbatim.

**Steps**:

1. In Settings, type `af-ZA` (Afrikaans) into the Language field (free-form input, not in the recommended datalist).
2. Trigger any LLM generation flow.

**Expected**:
- Setting is accepted, no validation error.
- Outgoing request shows `Accept-Language: af-ZA`.
- LLM response is in Afrikaans (best-effort — quality not guaranteed by this feature, only that the directive is forwarded faithfully).

---

## Scenario 7 — `localStorage` disabled / unavailable (edge case)

**Goal**: Verify graceful degradation when persistence is unavailable.

**Steps**:

1. In browser devtools, set up a profile where `localStorage` is blocked (or use a private window in Safari with strict settings, or override `Storage.prototype.setItem` in the console to throw).
2. Load the app.
3. Open Settings.

**Expected**:
- App loads without crashing.
- Settings panel shows Language derived from `navigator.language`.
- Attempting to change Language shows a console warning about persistence failure but does NOT crash.
- The runtime language for that session reflects the new value, but it does not persist past page reload.

---

## Scenario 8 — Domain Terminology mode remains orthogonal (FR-012)

**Goal**: Verify that the existing `displayName`-preference toggle composes cleanly with Language.

**Steps**:

1. Set Language to `en-US`.
2. Enable the "도메인 용어로 표시" (ubiquitous-language) toggle in Settings.
3. Open any existing domain entity (BoundedContext, Aggregate, etc.) that has a `displayName` populated (typically Korean for this codebase's existing data).
4. Trigger a generation flow that mentions this entity (e.g., a chat-modify request that references it).

**Expected**:
- The Korean `displayName` is rendered as-is in the UI labels (because the Terminology toggle is on).
- The generated narrative around it is in English (because Language is `en-US`).
- Mixed-language output is expected and correct: English prose containing Korean noun phrases that match the stored `displayName` values verbatim.

---

## Scenario 9 — Non-regression: existing endpoints still work without the header

**Goal**: Verify FR-013 — no breaking change to existing API contracts.

**Steps**:

1. Use any pre-existing integration test or curl invocation that does not set `Accept-Language`.
2. Run it against the post-feature backend.
3. Compare the response structure (JSON shape, status code, headers) to a recording of the pre-feature behavior.

**Expected**:
- Response JSON shape: identical.
- Status code: identical.
- Response headers: identical (no new `Content-Language` added; that's a non-contract per the contract doc).
- Only difference: response text content may now be in `en-US` if the pre-feature LLM happened to default to a different language. This is the intended behavior; FR-013 guarantees contract shape, not response-text-content stability.

---

## Acceptance gate

All nine scenarios MUST pass cleanly before this feature is considered ready for merge. Scenarios 1, 2, 4, and 5 are the load-bearing ones (US1, US2, US3, and FR-010 respectively). Scenarios 3, 6, 7, 8, and 9 verify the edge cases the spec called out.

Scenario 4 step 5 (AST regression test) and scenario 9 (non-regression) are also covered by the automated test suite — manual execution per this quickstart is the human-level smoke check, not a substitute for CI.
