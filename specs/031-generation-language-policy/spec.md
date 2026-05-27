# Feature Specification: Generation Output Language Policy

**Feature Branch**: `031-generation-language-policy`

**Created**: 2026-05-28

**Status**: Draft

**Input**: User description: "User story, acceptance criteria 생성 등 모든 생성시의 언어는 언어설정을 따라서 생성해줘야 하며, 언어설정은 톱니바퀴설정에서 할 수 있고, 기본은 사용자 접속 로케일을 따른다."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Locale-aware default for first-time users (Priority: P1)

A user opens the application for the first time on a Korean (or Japanese, English, etc.) operating system / browser. Without touching any setting, the user runs a workflow that generates new user stories and acceptance criteria. The natural-language portions of the generated artifacts (the "I want to / so that" clauses, Given/When/Then sentences, event/aggregate/command descriptions, BC narratives) come out in the language the user reads, every time.

**Why this priority**: This is the visible win of the policy. The product's value proposition is generation of design artifacts from natural-language input — if the output language does not match the user's reading language, the deliverable is unusable for the team. Zero-configuration default-correctness is what separates this from "yet another setting nobody finds."

**Independent Test**: With a clean browser profile whose locale is set to `ko-KR`, open the app, run the requirements ingestion → user-story planning flow on a sample input, and verify that every new natural-language string produced by the LLM is in Korean. Repeat with `en-US` and `ja-JP` locales. No manual Settings interaction is performed.

**Acceptance Scenarios**:

1. **Given** a fresh session in a browser whose `navigator.language` is `ko-KR`, **When** the user triggers user-story generation for a feature, **Then** the acceptance criteria sentences are produced in Korean.
2. **Given** a fresh session in a browser whose `navigator.language` is `en-US`, **When** the user triggers the same generation, **Then** the acceptance criteria sentences are produced in English.
3. **Given** a fresh session in a browser whose `navigator.language` is `ja-JP`, **When** the ingestion workflow auto-extracts events / aggregates / commands and writes natural-language descriptions for them, **Then** those descriptions are produced in Japanese while pre-existing user-supplied labels remain unchanged.

---

### User Story 2 - Explicit language switch via the gear-icon Settings (Priority: P2)

A user wants generated output in a language different from the one their OS/browser reports — for example, a Korean developer who collaborates with an English-speaking team and wants all newly generated documentation in English. The user opens the Settings panel (gear icon in the top bar), changes "Language" to `en-US`, closes the panel, and the very next generation call returns English output. The choice survives a page reload and a browser restart.

**Why this priority**: Without this control, locale-default behavior is a one-way door. Teams routinely produce artifacts in a non-native language for downstream consumers. The control must live in the same Settings surface as the existing Theme / Terminology / Domain Terminology toggles so users find it predictably.

**Independent Test**: Start a session whose default resolves to `ko-KR`. Open the gear icon, switch Language to `en-US`, close the panel. Trigger a new generation — verify English output. Reload the browser; verify the Settings panel still shows `en-US` and the next generation is still English. Clear localStorage; verify the default reverts to the browser locale.

**Acceptance Scenarios**:

1. **Given** a session whose effective Language is `ko-KR`, **When** the user opens Settings, selects `en-US`, and triggers a new user-story generation, **Then** the result is in English and the prior Korean artifacts are untouched.
2. **Given** the user has set Language to `en-US` and reloaded the page, **When** they open Settings, **Then** Language is still shown as `en-US` (persistence across sessions).
3. **Given** localStorage is cleared, **When** the user reloads the page, **Then** Language reverts to the value derived from `navigator.language`.

---

### User Story 3 - Single architectural touchpoint covers all current and future generation paths (Priority: P3)

A developer adds a new LLM-driven generation node next quarter — for example, a new "invariant suggestion" agent or a new export-document narrative writer. They wire it through the existing LLM-invocation layer and the language policy applies automatically: outputs follow the user's selected Language with no per-endpoint code changes, no new header to thread, no new contract field to plumb. Code review explicitly checks that any new generation path goes through this layer.

**Why this priority**: The product has dozens of LLM-call sites today (user_story_planning, ingestion workflow phases for events / aggregates / commands / UI wireframes, change_management planning, ddd_spec, requirements clarification, and more) and will grow more. A per-call-site patch will leave gaps; a single chokepoint will not. This story converts the policy from "we remembered to do it in N places" into "it is impossible to forget."

**Independent Test**: Audit every LLM invocation site in the codebase and confirm each one passes through the shared system-message / prompt-builder that injects the language directive. Add a deliberately new test fixture that invokes the LLM layer with `Accept-Language: ja-JP` and verify the system message contains a "Respond in ja-JP" instruction without any per-fixture configuration. A regression test catches any future LLM call that bypasses the shared layer.

**Acceptance Scenarios**:

1. **Given** the shared LLM-invocation entry point, **When** a request carries `Accept-Language: ko-KR`, **Then** every downstream LLM call within that request's scope receives a system-level instruction to respond in `ko-KR`.
2. **Given** a developer adds a new generation endpoint and routes its LLM call through the shared layer, **When** a user with Language=`ja-JP` triggers it, **Then** the output is in Japanese with zero per-endpoint configuration.
3. **Given** a developer accidentally writes a new generation endpoint that bypasses the shared layer, **When** the regression test suite runs, **Then** the test that asserts "all LLM call sites respect Accept-Language" fails and identifies the offending call site.

---

### Edge Cases

- **Unsupported / uncommon BCP-47 tag** (e.g., `af-ZA`, `xh-ZA`): the system passes the tag through to the LLM unchanged and lets the model handle it on a best-effort basis. The UI offers a recommended shortlist (`ko-KR`, `en-US`, `ja-JP`, `zh-CN`) but does not block free-form entry of any other valid BCP-47 tag.
- **`navigator.language` returns only a primary subtag** (e.g., `ko` instead of `ko-KR`): the system uses the value as-is — the LLM accepts either form.
- **localStorage is unavailable or disabled**: the system falls back to `navigator.language` on every load (no persistence) and does not crash. The Settings UI may show the value as "(not persisted)" or similar.
- **`Accept-Language` header is missing from the request** (e.g., a CLI or external system calling the backend without going through the SPA): the backend applies a server-side default language. See FR-010 for the chosen fallback.
- **A previously saved artifact exists in a different language** (e.g., user stories generated last week in Korean, user has now switched to English): the system does NOT retroactively translate; existing stored records keep their original language. Only newly generated content uses the current setting.
- **User-supplied input text is in language X but the setting says Y** (e.g., user types Korean event labels with Language=`en-US`): the system preserves the user's original text verbatim. Only LLM-generated commentary, descriptions, and Given/When/Then narration produced *from* that input are subject to the language policy.
- **LLM ignores the language instruction and outputs in the wrong language**: out of scope for this feature (best-effort dependency on the model). No fallback retry / translation pipeline.
- **Mixed-language session inside one ingestion workflow** (user switches Language mid-workflow): each LLM call uses whatever Language is current at the moment that call is made. The workflow does not lock in a Language at session start.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The Settings panel (opened from the gear icon in the top bar) MUST expose a "Language" control. It MUST sit alongside the existing Theme / Terminology / Domain Terminology controls so users discover it in the same place.
- **FR-002**: On first load (no previously stored value), the effective Language MUST be initialized from the user's browser locale, expressed as a BCP-47 tag (the value of `navigator.language`, e.g., `ko-KR`, `en-US`, `ja-JP`).
- **FR-003**: The user-selected Language MUST persist across page reloads and browser restarts on the same device/profile. Persistence MUST survive without server-side state (client-only storage is acceptable).
- **FR-004**: The user MUST be able to change the Language at any time from the Settings panel. The change MUST take effect on the next generation call without requiring a reload. Changing the Language MUST NOT alter or retranslate any previously stored artifact.
- **FR-005**: The application MUST attach the effective Language to every HTTP request that may trigger an LLM generation. Attachment MUST happen at a single global location in the HTTP client (so that every existing and future endpoint inherits it). The attachment MUST use a transport mechanism that a server-side framework can read uniformly (e.g., a standard request header).
- **FR-006**: At the backend request boundary, the inbound Language MUST be captured once and made available to every LLM-prompt builder invoked during that request, without each builder needing to receive it as an explicit parameter.
- **FR-007**: Every LLM call that produces natural-language output as part of any generation feature — including (but not limited to) user-story planning, acceptance-criteria authoring, requirements clarification, ingestion-workflow event / aggregate / command / UI-wireframe extraction, change-management planning, and DDD-spec narrative writing — MUST inject an instruction into the LLM's system message (or equivalent prompt position) directing the model to respond in the current Language.
- **FR-008**: The language-instruction injection MUST happen at a single shared chokepoint (a shared system-message builder, prompt-builder helper, or LLM-invocation wrapper). Individual generation features MUST NOT each implement their own injection. Adding a new generation feature later MUST NOT require touching language-policy code.
- **FR-009**: User-supplied input text (event labels, role names, action descriptions typed or pasted by the user) MUST be preserved verbatim by the system. The language policy MUST apply only to text that is newly generated, summarized, or rephrased by the LLM.
- **FR-010**: When an inbound request carries no Language indicator (no `Accept-Language` header or equivalent), the backend MUST apply a server-side default Language. The chosen default is [NEEDS CLARIFICATION: should the server-side fallback be `en-US` (broadest reader audience) or `ko-KR` (matches the current primary user base)?].
- **FR-011**: The system MUST accept any well-formed BCP-47 tag without erroring or substituting. Tags outside a curated recommendation list (e.g., `af-ZA`) MUST be passed to the LLM unchanged.
- **FR-012**: The Language policy MUST remain orthogonal to the existing Domain Terminology (ubiquitous-language) toggle. When `displayName` is present on a domain entity, it MUST continue to be displayed as-is regardless of Language. Language only governs newly generated natural-language prose, not stored proper nouns.
- **FR-013**: Language attachment MUST NOT require any change to existing API contracts beyond a single header at the HTTP boundary. No new request-body fields and no new query parameters are introduced.
- **FR-014**: The system MUST NOT introduce any new persisted schema for the Language value on the server side. The selected Language is a per-request, client-derived value — not a stored user profile attribute (at least in this feature; a future feature may add server-side user profiles).
- **FR-015**: A regression test MUST exist that fails if any new LLM-invocation site is added without going through the shared chokepoint described in FR-008.

### Key Entities

- **Effective Language (client-side)**: A BCP-47 tag held in the client. Resolved at app startup from (1) persisted user choice if present, otherwise (2) `navigator.language`. Mutable from the Settings panel. Travels on every outbound API request.
- **Language Context (server-side, per-request)**: The inbound language value made available to all generation code paths for the duration of one HTTP request. Not persisted. Defaults applied if absent (see FR-010).
- **Generated Natural-Language Output**: Any LLM-produced prose — acceptance-criteria sentences, descriptions, summaries, narrative — that is subject to the Language policy. Distinct from user-supplied input text and from structural identifiers, both of which are preserved verbatim.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A first-time user whose browser locale matches one of `ko-KR`, `en-US`, `ja-JP` sees 100% of newly-generated acceptance-criteria sentences in their browser's language, with zero Settings interaction.
- **SC-002**: After a user explicitly changes Language in Settings, ≥99% of natural-language strings produced by the next generation call match the chosen Language (measured by automated language-detection on the output strings of a fixture run).
- **SC-003**: The user's Language selection survives a browser restart in 100% of sessions where localStorage (or equivalent client storage) is functional.
- **SC-004**: 100% of existing LLM generation features (user-story planning, ingestion workflow event/aggregate/command/UI-wireframe extraction, requirements clarification, change-management planning, DDD-spec narrative) honor the Language selection after this feature ships. Verified by an audit table mapping each LLM call site to the shared chokepoint.
- **SC-005**: A future developer can add a new LLM-driven generation endpoint without writing any language-handling code, and their endpoint automatically produces output in the user's selected Language. Verified by a deliberate "new endpoint" test fixture added in this feature's tests.
- **SC-006**: Zero existing API contracts are broken by this feature. No request-body shape changes; only a single header is added at the HTTP boundary.
- **SC-007**: Previously-stored generated artifacts are not modified by this feature. A before/after diff of the artifact store shows zero retroactive changes.

## Assumptions

- Generation features today either already share an LLM-invocation layer or can be refactored to share one with bounded effort. If they do not, the implementation plan must include that refactor as a prerequisite — without it, FR-008 (single chokepoint) cannot be met.
- BCP-47 tags displayed as raw strings in the Settings UI (e.g., `ko-KR`, `en-US`) are acceptable to users. A friendlier label mapping ("한국어 (ko-KR)", "English (US)") is a nice-to-have but not required for v1.
- LLM models in use (whichever provider is active per [api/platform/llm.py](api/platform/llm.py)) can follow a "Respond in {BCP-47 tag}" instruction with reasonable fidelity for the recommended shortlist (`ko-KR`, `en-US`, `ja-JP`, `zh-CN`). Quality for long-tail tags is best-effort.
- The product's UI itself (menu labels, button text, tooltips, modal copy) is out of scope for this feature. UI internationalization is a separate effort. This feature governs only LLM-generated content.
- The Electron desktop shell (active feature 023, currently paused) will, when resumed, forward the OS locale into the bundled web app via the same `navigator.language` path or equivalent. No special desktop-shell coupling is needed in this feature; the shell hosts the same SPA and inherits the same behavior.
- "Domain Terminology" mode (existing `displayName` preference in Settings) remains orthogonal: `displayName` overrides are not retranslated or affected by Language selection. The two settings compose cleanly.
- Existing stored artifacts (user stories, events, aggregates, etc.) are not retranslated by this feature. Retroactive translation, if ever needed, will be a separate feature with its own UX (user-initiated, per-artifact).
- The backend is a single FastAPI app per [api/](api/). No multi-service request-context propagation is required for this feature; the contextvar approach implied by FR-006 stays in-process.
- No Neo4j schema change, no new Pydantic model, no new persisted field on the server side. The Language value lives entirely in the request lifecycle and the client.
