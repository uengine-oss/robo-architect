# Feature Specification: Figma Document Binding for Event Modeling

**Feature Branch**: `016-figma-document-binding`
**Created**: 2026-05-07
**Status**: Draft
**Input**: User description: "상단 탭에 Figma 버튼을 두고 클릭 시 연동할 Figma 다큐먼트를 선택. 선택된 Figma 문서와 동기화되어 Event Modeling의 각 페이지(=Business Process)가 해당 Figma 다큐먼트의 페이지에 1:1로 매핑됨. Design 탭에서 UI를 생성할 때 Figma 바인딩이 있으면 HTML 와이어프레임이 아니라 Figma 프레임으로 생성되어 연결된 다큐먼트에 들어가도록 동작. 기존 009-figma-sync-bidirectional 스펙과 충돌하지 않게 보강."

## Clarifications

### Session 2026-05-07

- Q: Bulk 인제스션의 `Figma UI` 모드와 FigmaBinding 의 관계는? → A: bulk 모드 자체는 binding-independent (sceneGraph 만 채움). 하지만 binding 이 active 인 상태로 bulk 가 돌면, sceneGraph 채우기에 더해 Figma 문서 측에도 storyboard 페이지 / 프레임을 함께 동기화한다. Figma 측 동기화가 실패해도 ingestion 은 멈추지 않고 진행을 계속하며, 실패한 항목은 사용자에게 표시되어 나중에 재시도할 수 있어야 한다.
- Q: Bulk ingestion 중 사용자가 취소했을 때의 의미는? → A: 현재 batch(최대 10개) 가 자연 완료될 때까지 기다린 뒤 중단. 이미 시작된 retry 는 정상 완료까지 진행. UI 노드(작성된 sceneGraph 포함) 는 모두 보존되며 롤백 없음.
- Q: FR-018 한글 폰트 preload 가 실패했을 때 UX 는? → A: 앱 boot 은 차단하지 않음. FrameEditor 가 처음 마운트될 때 등록 상태를 확인해 폰트가 없으면 캔버스 위에 1회 한국어 배너 "한글 폰트 로드 실패 — 새로고침을 시도해 주세요" 를 표시. 다른 기능(인제스션, 데이터 모델링) 은 정상 동작.
- Q: FR-020 의 "Figma 동기화 실패 항목" 리스트 / "다시 시도" 컨트롤은 어디에 노출되나? → A: 두 곳에 모두 노출. (1) ingestion floating panel 의 summary 영역에 "Figma 동기화 실패 N건" 섹션 — 노드 목록 + "전체 다시 시도" + 노드별 "다시 시도" 버튼. (2) 각 UI 노드의 Inspector Design 탭에 빨간 배지 — 노드별 "다시 시도" 컨트롤.
- Q: Bulk ingestion 이 binding active 상태에서 돌 때, 이미 sceneGraph 가 있는 UI 노드(FR-012 conflict) 의 처리는? → A: bulk 경로는 FR-012 모달을 우회하고 항상 overwrite (새 sceneGraph 로 덮어씀). 사용자가 ingestion 시작 시 "삭제하고 계속" 을 눌러 명시적 의사를 이미 표현했기 때문. FR-012 의 prompt 는 per-node on-demand 생성에만 적용.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Connect an Event Modeling project to a Figma document (Priority: P1)

The architect clicks a "Figma" control in the application top bar (alongside `문서 업로드` / `PRD 생성` / `Claude Code` / `설정`), pastes a Figma file URL or file key plus a personal access token (if not already stored), and confirms. After confirmation, the application stores the link between this Event Modeling project and that Figma document. A status indicator on the top bar reflects that a document is linked.

**Why this priority**: Without this connection step, no other behavior in this feature can run. It is the entry point users must reach first.

**Independent Test**: Open the app with an Event Modeling project loaded → click the new Figma control in the top bar → enter token + file URL → confirm → verify a "Connected to <file name>" indicator appears in the top bar. Reload the page and verify the binding persists.

**Acceptance Scenarios**:

1. **Given** no binding exists, **When** the user clicks the Figma control, **Then** a connection panel appears prompting for a Figma file URL/key (and a token if none is stored).
2. **Given** valid token + reachable file key, **When** the user confirms, **Then** the application records the binding and surfaces a "Connected to <file name>" indicator in the top bar.
3. **Given** an invalid token or unreachable file, **When** the user confirms, **Then** the binding is not saved and a clear Korean error explains why.
4. **Given** an existing binding, **When** the user clicks the Figma control again, **Then** they see options to view the linked file, replace the binding, or disconnect.

---

### User Story 2 - Each Event Modeling storyboard maps to a Figma page (Priority: P1)

After binding, the application ensures the linked Figma document contains one page per storyboard listed for the current Event Modeling project (one row in the `BUSINESS PROCESSES` panel = one storyboard). Pages that already exist in Figma are reused when matched by stable mapping ID; missing pages are created and named after the storyboard's entry command display name (e.g., `상품 등록`, `주문하기`).

**Why this priority**: Pages are the destination for every UI frame the next user story will generate. Without correct page mapping, generated frames would land in arbitrary locations.

**Independent Test**: Bind to an empty Figma document while the local project has 5 storyboards → verify that the linked document now contains 5 pages with the same names, in the same order as the left-panel list, and that re-running sync is idempotent.

**Acceptance Scenarios**:

1. **Given** a fresh binding and 5 local storyboards, **When** sync runs, **Then** the linked document contains 5 pages whose names match each storyboard's entry command display name exactly.
2. **Given** a storyboard is renamed locally (its entry command's display name changes), **When** the next sync runs, **Then** the corresponding Figma page is renamed (matched by stable mapping ID, not by name).
3. **Given** a storyboard is removed locally (entry command deleted, or it is no longer an entry — e.g. became policy-invoked), **When** the next sync runs, **Then** the corresponding Figma page mapping is archived (the page itself is left intact in Figma) and the archive entry appears in the binding history.
4. **Given** the linked file already contains unrelated pages, **When** sync runs, **Then** unrelated pages are left untouched and only missing mapped pages are created.

---

### User Story 3 - UI generation targets the linked Figma document instead of HTML (Priority: P1)

When the architect opens the Design tab on a UI node and clicks a generate action (`Component로 생성` or `OpenPencil AI로 생성`), and the project has an active Figma binding, the system creates a new Figma frame in the page corresponding to the UI node's owning storyboard — instead of producing an HTML wireframe locally. The Design tab then renders the linked Figma frame for review/edit. The UI node records that its design source is `figma-bound` and stores the `{file key, page id, node id}` triple.

**Why this priority**: This is the user-visible payoff of the binding. Without it, the binding stays decorative.

**Independent Test**: With a Figma binding active, open Design tab on a UI node that has no design yet → click `Component로 생성` → verify (a) a new frame appears in the correct Figma page in the linked document, (b) Design tab shows that frame, (c) HTML wireframe generation paths were not invoked for this node.

**Acceptance Scenarios**:

1. **Given** an active binding and a UI node with no scene graph, **When** the user generates a design, **Then** a Figma frame is created in the Figma page corresponding to the UI node's owning storyboard and the UI node's design source is recorded as `figma-bound`.
2. **Given** an active binding, **When** the user generates a design, **Then** HTML wireframe generation paths are not invoked for that generation.
3. **Given** no binding is active, **When** the user generates a design, **Then** the existing HTML / Component wireframe behavior is preserved unchanged.
4. **Given** a UI node already has a scene graph from prior HTML generation and binding becomes active, **When** the user clicks generate again on that node, **Then** the user is prompted to choose between (a) overwriting with a new Figma generation or (b) importing the existing scene graph into the linked Figma document; the outcome reflects the chosen option.

---

### User Story 4 - Disconnect or replace the linked Figma document (Priority: P2)

The architect can disconnect the binding or replace it with another Figma document at any time. Disconnection does not delete previously created Figma frames or local scene graphs; subsequent generations on new nodes revert to HTML mode. Replacing the binding triggers re-mapping of business-process pages against the new document; old per-node Figma references are flagged as "from previous binding" but are not auto-migrated.

**Why this priority**: Required for projects that change designers, change Figma workspaces, or want to detach the integration. Important but not blocking the core value of US1–US3.

**Acceptance Scenarios**:

1. **Given** an active binding, **When** the user disconnects, **Then** the binding is removed and the top-bar indicator clears; existing UI scene graphs and previously created Figma frames remain intact.
2. **Given** an active binding, **When** the user replaces it with a different Figma file, **Then** the new file is bound, missing pages are created in the new file, and per-node Figma references from the old file are marked `from previous binding`.

---

### Edge Cases

- A UI node was previously linked to a different Figma file via spec 009 per-node sync — per-node bindings remain authoritative for their own pull/push operations; document-level binding governs only **new** generations going forward.
- Two storyboards share the same entry-command display name — Figma pages are deduplicated with a numeric suffix; mapping uses internal stable IDs so future renames are non-destructive.
- The linked Figma document is deleted or has its access revoked in Figma — the next sync attempt surfaces a clear Korean error and offers to disconnect or re-link.
- Generation invoked while Figma is unreachable — generation fails with a Korean error explaining the disconnection; the user can retry or temporarily disconnect to use HTML mode.
- The architect generates designs for many UI nodes concurrently — generation requests are queued and applied to the linked Figma document one at a time per page to respect Figma rate limits.
- **Bulk ingestion-time figma generation** — When the architect picks `Figma UI` mode at the upload modal, the ingestion phase fans out one JSX-agent invocation per Command/ReadModel UI in batches of 10 (`asyncio.gather`). The shared wireframe-service (Bun, `:7610`) cannot keep up with that fan-out and used to time out / drop request bodies (`Unexpected end of JSON input`) on roughly 40% of the batch, leaving those UI nodes with empty `sceneGraph`. After the v1.1 reliability hardening (FR-017) the system absorbs these transient failures so every UI node ends with a non-empty `sceneGraph` under normal operation.
- **Korean text in the Design tab canvas** — the Design tab's open-pencil `FrameEditor` runs an in-browser CanvasKit renderer which keeps its own typeface registry, separate from the browser's CSS font stack. open-pencil's default CJK fallback chain (`window.queryLocalFonts` → Google Fonts metadata API) cannot be relied on in this app: the Permissions API requires a user gesture before mounting the canvas, and the metadata API key shipped by upstream is rate-limited (HTTP 429) under shared use. The system MUST bundle a Korean-capable typeface so Hangul does not render as tofu (□□□) in any FrameEditor instance.
- The Event Modeling project is duplicated/cloned — the binding is intentionally **not** carried over; the new copy starts unbound.
- A storyboard's order changes in the left panel (different entry-command ordering) — the corresponding Figma page is reordered to match (best-effort) but the mapping ID does not change.
- A UI node is reachable from multiple entry commands — the deterministic resolver picks the entry command with the lexicographically earliest display name (then by command id); the choice is recorded in the binding history for traceability.
- A UI node is not reachable from any entry command (orphan) — generation surfaces a clear Korean error and offers a per-node fallback to HTML mode (the user can choose to skip Figma for this node, or fix the model so the UI is reachable).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST display a Figma control in the application top bar (in the same row as the existing `문서 업로드`, `PRD 생성`, `Claude Code`, and `설정` controls) whose visual state reflects current binding status (connected / disconnected).
- **FR-002**: System MUST allow the architect to bind the current Event Modeling project to a Figma document by providing a Figma file URL or file key plus (when not already stored) a Figma personal access token.
- **FR-003**: System MUST validate the binding by fetching basic file metadata from Figma before persisting; on failure, the binding MUST NOT be saved and a clear Korean error MUST be shown to the user.
- **FR-004**: System MUST persist the binding (Event Modeling project ↔ Figma file key + display name + connected timestamp + last sync timestamp) so that the binding survives page reload and is shared by all collaborators on the same Event Modeling project.
- **FR-005**: System MUST allow the architect to disconnect or replace the binding from the same Figma control. Disconnection MUST NOT delete previously generated Figma frames or local scene graphs.
- **FR-006**: When a binding is active, System MUST ensure the linked Figma document contains exactly one page per storyboard in the current Event Modeling project, creating missing pages and reusing pages matched by stable mapping ID.
- **FR-007**: System MUST track the mapping between each storyboard and its Figma page using a stable internal mapping ID so that renames in either side do not break the mapping.
- **FR-008**: System MUST rename the corresponding Figma page when a storyboard is renamed locally (i.e. the entry command's display name changes); symmetric Figma-side renames MUST be reflected on the local storyboard at next sync.
- **FR-009**: When a storyboard is removed locally with binding active (its entry command is deleted, or the command is no longer an entry — e.g. it became policy-invoked), System MUST archive the corresponding mapping (leaving the Figma page itself untouched) and record the archive event in the binding history.
- **FR-010**: When the architect triggers UI generation on a UI node and a Figma binding is active, System MUST resolve the UI's owning storyboard (deterministic resolver), create a Figma frame in that storyboard's page, and record the resulting `{file key, page id, node id}` triple as the UI node's `figma-bound` design source. If the UI is not reachable from any storyboard, System MUST surface a clear Korean error and offer the architect a per-node fallback to HTML mode (no silent fallback).
- **FR-011**: When a Figma binding is active, System MUST NOT invoke HTML wireframe generation for new UI generations; HTML mode remains the default only when no binding is active.
- **FR-012**: When a UI node already has a scene graph and binding is active, System MUST prompt the architect to choose between overwriting with a fresh Figma generation or importing the existing scene graph into the linked Figma document; both outcomes MUST be recorded in observability events. **Scope**: this prompt applies only to *per-node, on-demand* generation triggered from the Inspector (`Component로 생성` / `OpenPencil AI로 생성`). The bulk ingestion path under FR-019 MUST NOT show this prompt — it always overwrites, because the architect already made the destructive intent explicit by confirming "기존 데이터 삭제하고 계속" at the upload modal.
- **FR-013**: System MUST surface, on the Design tab of every UI node under an active binding, a clear indicator of which Figma file/page/frame the node is linked to and a control to open that frame directly in Figma.
- **FR-014**: System MUST log all binding lifecycle events (connect, validate, sync pages, page rename, page archive, disconnect, replace) and every UI generation routing decision (HTML vs Figma-bound) with structured events for observability.
- **FR-015**: System MUST gracefully degrade when the linked Figma document is unreachable: surface a Korean error, block new Figma-targeted generations, and offer a one-click temporary disconnect that allows HTML mode to be used until Figma access is restored.
- **FR-016**: System MUST NOT carry the binding when an Event Modeling project is duplicated or cloned; the new copy begins unbound.
- **FR-017**: System MUST absorb transient failures from the wireframe rendering service (Bun, `:7610`) when generating Figma-mode UI wireframes in bulk. A single render call MUST NOT cause an empty `sceneGraph` to be persisted — the system MUST retry transparently in the renderer-call layer (transport-level retries with backoff), in the agent loop (re-issue the last successful JSX as a final fallback when the LLM gives up after a tool-error turn), and in the figma-mode wrapper (whole-agent retries with jittered backoff). Under nominal load (10 concurrent UI generations during ingestion), every UI node MUST end the ingestion with a populated `sceneGraph`.
- **FR-018**: System MUST guarantee that the Design tab's in-browser CanvasKit renderer can draw Hangul glyphs without depending on the browser's local-font Permission API or external font metadata services. A Korean-capable typeface MUST be served from the application's own static assets and registered into open-pencil's font registry before any FrameEditor mounts, so a fresh page load in a private/offline-ish environment still renders Korean text correctly. If the preload itself fails (asset missing, network error, CSP block), the system MUST NOT block app boot or other features; instead, when a FrameEditor mounts and the Korean fallback typeface is not registered in open-pencil's font registry, the system MUST display a single non-blocking Korean banner over the canvas reading "한글 폰트 로드 실패 — 새로고침을 시도해 주세요". The banner MUST appear at most once per page load and MUST NOT prevent interaction with the canvas itself.
- **FR-019**: The ingestion modal's `Figma UI` mode (bulk wireframe generation during requirement ingestion) MUST be independent of FigmaBinding: it always populates each UI node's `sceneGraph` regardless of whether a binding is active. When a binding **is** active at ingestion time, the system MUST additionally (a) ensure each storyboard's Figma page exists in the linked document (same logic as on-demand sync from FR-006), and (b) push each generated UI as a Figma frame into its storyboard's page (same logic as on-demand generation from FR-010). When **no** binding is active, the bulk path stops at populating `sceneGraph` only — no Figma writes are attempted. This means `ui_generation_mode=figma` is a *storage-format* choice, not a *destination* choice; the destination is determined entirely by binding state.
- **FR-020**: Failures of Figma-side synchronization during bulk ingestion (page creation, frame push, plugin unreachable, rate limit) MUST NOT halt the ingestion or roll back already-completed work. The ingestion continues to its normal end; per-UI Figma push failures are recorded against the affected UI node (status flag + last error) and surfaced to the architect as a list of "Figma 동기화에 실패한 항목" with a "다시 시도" control that re-runs the push for the listed nodes against the still-active binding. The Korean-language error stays attached to each UI node until a successful retry clears it. The failure list and retry controls MUST be exposed in **both** of these surfaces:
  1. The ingestion floating panel's summary area (shown when ingestion completes) MUST contain a "Figma 동기화 실패 N건" section listing each failed UI by display name + last error, a "전체 다시 시도" button that re-runs the push for the whole list, and a per-node "다시 시도" button.
  2. Each affected UI node's Inspector Design tab MUST show a red badge ("Figma 동기화 실패") with a per-node "다시 시도" control that calls the same retry path as (1).
  The two surfaces share the same per-UI status flag and history entries — retrying from either clears the flag once successful.
- **FR-021**: When the architect cancels a running bulk ingestion (existing `/api/ingest/{session_id}/cancel` endpoint), the workflow MUST let the *current* concurrent batch (BATCH_SIZE up to 10 UI generation tasks) and any retries that have already started complete naturally — no pre-emption of in-flight LLM calls or wireframe-service requests — and then stop before the next batch dispatches. UI nodes already written to Neo4j MUST be preserved verbatim (no rollback); a UI node whose generation hadn't started before the cancel signal MUST simply not be created. Subsequent re-ingestion or per-node retry is the architect's path to fill the gap.

### Key Entities

- **EventModelingProject** (existing): the project root; gains an optional reference to a single FigmaBinding.
- **FigmaBinding**: the link between one Event Modeling project and one Figma document. Carries file key, file display name, who connected it, when, last successful sync time, status (`active` | `unreachable` | `disconnected`).
- **Storyboard** (conceptual, not a stored entity): one row in the left-panel `BUSINESS PROCESSES` list. Each storyboard is the vertical slice anchored on one user-initiated entry command and the UI screens, events, and read models reachable from it. The storyboard's stable identity is the entry command's ID. (Implementation note in plan/research/data-model: this is a `:Command` that is not invoked by any `:Policy` — there is no separate `:Storyboard` Neo4j label.)
- **StoryboardPageMapping**: per-storyboard record carrying `{storyboardId (= entry command id), figmaPageId, mappingId, status (active|archived), lastRenameAt}`.
- **UIDesignSource**: per-UI-node record carrying which generation source produced the current scene graph (`html` | `figma-bound` | `imported`); for `figma-bound` and `imported`, also stores `{figmaFileKey, figmaPageId, figmaNodeId}`.
- **BindingHistoryEvent**: append-only record of binding lifecycle events for audit and operability (connect, validate failure, sync, rename, archive, disconnect, replace, generate routed, orphan UI blocked).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An architect can complete the first-time Figma binding (open control → paste URL → enter token → confirm) in under 60 seconds when given valid credentials.
- **SC-002**: After binding to a fresh Figma document, all storyboard pages exist in the linked document within 5 seconds for projects of up to 25 storyboards.
- **SC-003**: Generating a new UI design with an active binding produces a visible frame in the correct Figma page within 15 seconds for at least 90% of attempts under normal network conditions.
- **SC-004**: For UI nodes generated while a binding is active, 100% have their design source recorded as `figma-bound` and reference a Figma frame that exists in the linked document at sync time.
- **SC-005**: When the architect disconnects the binding, subsequent generations on new nodes fall back to HTML wireframe mode in 100% of cases without requiring a page reload.
- **SC-006**: After two weeks of binding being active on a project, at least 80% of newly created UI nodes in that project have `figma-bound` as their design source (qualitative adoption measure).
- **SC-007**: Bulk ingestion in Figma UI mode produces 100% populated `sceneGraph`s for the built-in food-delivery sample (19 UIs) on a developer laptop with the wireframe service running locally. Measured by the diagnostic Playwright run `frontend/tests/figma-ui-bulk-diag.spec.ts`. Baseline before reliability hardening: 11/19 (42% empty). Post-fix target: 19/19. Sustained ≥ 95% across re-runs is the acceptance bar for the requirement to be considered met.
- **SC-008**: A fresh page load with no cached fonts and no granted local-font permission renders all Korean labels in any FrameEditor instance (no tofu glyphs). Measured by the diagnostic Playwright run `frontend/tests/font-loading-diag.spec.ts`, which probes `/Inter-Regular.ttf` and `/Pretendard-Regular.otf` for non-HTML payloads and asserts the absence of `OTS parsing error` / `Failed to load font` console messages.

## Assumptions

- A "page in Event Modeling" maps 1:1 to a **storyboard** — one row in the left-panel `BUSINESS PROCESSES` list. Each storyboard is the vertical slice anchored on one user-initiated entry command (and the UI screens, events, and read models reachable from it); a single Bounded Context typically contains many such storyboards. UI nodes are assigned to a storyboard at sync/generate time by reachability from each entry command (mirror of the same chain-building logic the navigator already uses to populate the panel); deterministic tie-break: the canonical ordering of entry commands by display name.
- Figma authentication reuses the existing pattern from spec 009 (`personal access token entered by the user`); token storage location (browser local storage vs server-side) follows whatever 009 already established and is not redefined here.
- The linked Figma document is a shared file and the connecting user has at least edit permission on it.
- "Generate" in the Design tab covers both `Component로 생성` and `OpenPencil AI로 생성` paths; both routes flow into Figma when the binding is active.
- Per-node Figma sync from spec 009 (pull/push of an individual UI node ↔ a specific Figma frame, plus the live plugin channel) continues to function and is not removed by this feature; document-level binding only governs **new** generations and supplies a default destination.
- The new Figma frame is created in Figma using whichever mechanism spec 009 already uses for write operations (REST or plugin); this spec does not redefine the underlying mechanism, only the routing rule (when binding is active, route to Figma; otherwise HTML).
- Spec 009 will need targeted, additive updates to (a) acknowledge document-level binding when present and (b) document the precedence rules (per-node bindings are authoritative for their own sync; document-level binding governs new generations and the default destination). Those edits live in spec 009's own update PR, not in this feature's scope.
- Conflict between this binding and any other concurrent collaborative editing happening in the linked Figma file is the architect's responsibility; the system does not arbitrate Figma-side concurrent edits.
- Branch creation (`016-figma-document-binding`) is the user's choice and is not performed by this command; the spec directory under `specs/` and the branch name are independent.
