# Feature Specification: Figma Sync Recovery & Retroactive Push

**Feature Branch**: `020-figma-sync-recovery`
**Created**: 2026-05-08
**Status**: Draft
**Input**: User description: "연동 피그마에 반영하는 옵션이 이미 있거나 혹은 피그마에 반영하지 않은 옵션이 켜져 있지 않았을 경우 여기서 피그마에 반영을 다시 시킬 수 있는 그리고 만약에 반영 시도를 했었는데 실패한 이력이 있다면 그 로그가 여기에 나왔고 그것을 다시 리트라이 시킬 수 있는 그런 버튼 기존 옵션에서 피그마 다큐먼트가 있지만 피그매로 연동을 안시켰을 때 사후에 연동도 시킬 수 있고 그리고 기술적 이유로 오류가 났었어도 연동이 될 수 있도록 여기서 조치할 수 있는 화면들을 만들어주고자 하는 거야."

## Clarifications

### Session 2026-05-08

- Q: "전체 Figma 반영" 트리거의 동작 범위는? → A: **Generate + Push** — sceneGraph가 없는 UI 노드도 figma 모드로 생성하면서 Figma 프레임을 함께 만든다. (그 결과 한 번의 트리거로 프로젝트 전체가 Figma 측에 반영된다.)
- Q: 이미 HTML 모드 sceneGraph 가 존재하는 UI 노드의 충돌 처리는? → A: **prompt 없이 덮어쓰기** — 사용자가 이 화면에서 "전체 Figma 반영"을 명시적으로 선택했으므로 016 의 bulk 경로(FR-019) 와 동일하게 prompt 를 우회하고 항상 overwrite 한다.
- Q: 이력(History) 탭의 표시 수준은? → A: **실패 + 요약만** — 실패 이벤트는 상세히(재시도 버튼 포함), 성공은 "YYYY-MM-DD 전체 동기화 — 페이지 N건 / 프레임 M건 성공" 식으로 한 줄 요약. lifecycle 이벤트의 모든 입자를 다 노출하지 않는다.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Retroactively push an unsynced project to Figma (Priority: P1)

The architect previously bound their Event Modeling project to a Figma document (per spec 016) but ran requirements ingestion in HTML mode (the `Figma UI` toggle was off), so the linked Figma document is empty of storyboard pages and UI frames even though a binding exists. The architect now decides "I want this project mirrored in Figma" and opens the Figma 다큐먼트 연동 modal. From there they trigger a single "전체 Figma 반영" action that creates all storyboard pages, generates Figma-mode designs for every UI node that lacks one, and pushes them as frames into the corresponding pages. While the operation runs, the modal shows progress (storyboards X/Y, UIs A/B). When it ends, every storyboard has a Figma page and every UI node either is `figma-bound` or appears in a residual failure list with a retry control.

**Why this priority**: This is the primary motivating use case. Without it, a project bound late-in-life or by a user who forgot to enable Figma UI mode at ingestion stays out of sync forever — the only escape today is "delete and re-ingest with the toggle on", which is destructive and slow.

**Independent Test**: Take a project with an active binding and 5 storyboards / 19 UIs all in HTML mode (no `figma-bound` design source) → open the modal → trigger 전체 Figma 반영 → verify (a) the linked Figma document gains 5 pages with the correct storyboard names, (b) all 19 UI nodes end up `figma-bound` referencing frames inside the right pages, (c) HTML scene graphs are overwritten without per-node prompts, (d) progress is visible during the operation and a final summary is shown.

**Acceptance Scenarios**:

1. **Given** an active binding and a project where no UI is yet `figma-bound`, **When** the architect clicks "전체 Figma 반영" in the modal, **Then** the system creates missing storyboard pages, generates Figma-mode designs for UIs without one, pushes frames for UIs whose sceneGraph already exists in another mode, and reports a single success/failure summary at the end.
2. **Given** a UI node already has an HTML-mode sceneGraph, **When** retroactive sync runs, **Then** that sceneGraph is overwritten with a Figma-mode generation without showing the per-node 016 FR-012 prompt, and a "previous sceneGraph 덮어쓰기" line is recorded in the history.
3. **Given** retroactive sync is running, **When** the architect tries to trigger it again, **Then** the second trigger is disabled with a Korean message indicating sync is in progress; live progress (storyboards X/Y, UIs A/B) is visible.
4. **Given** retroactive sync is running, **When** the architect clicks 취소, **Then** in-flight items complete naturally, no new dispatches are made, and the unsent items remain in "not yet synced" state (not marked as failures).
5. **Given** retroactive sync completes with some items succeeding and some failing, **When** the modal returns, **Then** the History tab shows one summary row for the successes and individual failure rows with retry buttons.

---

### User Story 2 - Retry individual items that failed Figma sync (Priority: P1)

After bulk ingestion in Figma mode (per 016 FR-019/FR-020) — or after a previous retroactive sync from US1 — some items remain marked as failed: Figma rate limits hit a few frames, the Figma plugin was momentarily unreachable, a 5xx response timed out a page creation. The architect opens the Figma 다큐먼트 연동 modal → 이력 (History) tab and sees a list of these failures with a Korean error per row. Each row has a "다시 시도" button; a "전체 다시 시도" button at the top of the failure list re-runs every retryable failure. After successful retry, the failure is cleared from the list and from the other surfaces in the system (ingestion floating panel summary, Inspector Design tab red badge) because they share the same store.

**Why this priority**: Today the only retry surfaces are the ingestion floating panel (transient — disappears once dismissed) and per-node Inspector badges (requires opening each affected node). The modal becomes the durable, project-level hub for sync recovery, which is essential when failures span many nodes or accumulate over time.

**Independent Test**: Force three Figma push failures during bulk ingestion → close the floating panel → open the Figma 다큐먼트 연동 modal → 이력 tab → verify all three failures appear with "다시 시도" buttons → click "전체 다시 시도" → verify all three succeed and are removed from both this view and the Inspector badges on the same nodes.

**Acceptance Scenarios**:

1. **Given** N retryable Figma sync failures exist for the project, **When** the architect opens the History tab, **Then** all N failures are listed with display name, last error (Korean), and a "다시 시도" control per row.
2. **Given** at least one retryable failure exists, **When** the architect clicks "전체 다시 시도", **Then** every retryable failure is re-run against the active binding; failures that succeed disappear from the list, failures that re-fail update their last-error timestamp.
3. **Given** the Inspector Design tab of the same UI node currently shows a red "Figma 동기화 실패" badge, **When** the architect retries that failure successfully from the modal, **Then** the Inspector badge clears without a page reload.
4. **Given** a failure is non-retryable (Figma file deleted, access revoked, the storyboard was archived locally), **When** it appears in the History tab, **Then** it is marked "재시도 불가" with an explanatory Korean reason and shows no retry button.
5. **Given** the binding is currently disconnected (or marked unreachable), **When** the architect opens the History tab, **Then** historical entries render read-only and all retry buttons are disabled with a Korean note explaining why.

---

### User Story 3 - Audit-quality view of past sync activity (Priority: P2)

The architect wants to know "when did this project last sync to Figma? what changed?" The History tab shows, in reverse-chronological order: failure rows (detailed, with retry where applicable) interleaved with one-line summary rows for successful sync runs ("2026-05-08 14:22 — 전체 동기화: 페이지 5건 / 프레임 17건 성공, 2건 실패"). This gives the architect enough context to understand sync state without the noise of every individual page-create / frame-push event.

**Why this priority**: Improves operability and trust — important once the project has been worked on for a while, but not blocking the core value of US1 + US2.

**Acceptance Scenarios**:

1. **Given** the project has had 3 retroactive sync runs and 2 individual retry runs, **When** the architect opens the History tab, **Then** they see at most 5 summary rows for the runs (newest first) plus any still-failing items pinned at the top.
2. **Given** a previous binding (now replaced) had its own history, **When** the architect opens the History tab, **Then** entries from the previous binding are visually grouped under "이전 바인딩" and are read-only / non-retryable.
3. **Given** no sync activity has ever occurred for the project, **When** the architect opens the History tab, **Then** an empty-state Korean message ("이력 없음 — '연결 상태' 탭에서 전체 Figma 반영을 시작할 수 있습니다") is shown.

---

### Edge Cases

- The architect triggers retroactive sync but the binding became unreachable since they last opened the modal (Figma file deleted, token expired, network down) — the sync is aborted before any item dispatches, the modal surfaces the same Korean error 016 FR-015 already mandates, and no spurious failure rows are created.
- Two collaborators on the same project trigger retroactive sync simultaneously — only the first holds the lock; the second sees a Korean message that another user is currently syncing and may join the progress view but cannot dispatch a competing run.
- The architect retries from the modal at the same moment another user retries the same failure from the Inspector badge — the second retry detects the in-flight retry and joins it (or no-ops) rather than firing a duplicate Figma request.
- A retryable failure has been pending for so long that the underlying storyboard was deleted locally — on retry, the system detects this, transitions the failure to "재시도 불가 — 스토리보드 없음", and removes the retry button.
- The architect cancels an in-progress retroactive sync — UI nodes that completed (figma-bound) and pages that were created stay; UIs not yet attempted remain in "not yet synced" state and can be picked up by a future sync without losing prior progress.
- Retroactive sync exceeds Figma rate limits mid-run — the controller backs off and continues; per-item failures that exhaust their retry budget end up as failure rows in History; the run does not abort.
- The full-sync action is invoked while no binding is active — the action is hidden / disabled in the modal; the user must first connect via the Connect tab.
- A project with hundreds of UIs triggers retroactive sync — the system runs in batches under the same concurrency cap as bulk ingestion (per 016 FR-019 fan-out semantics) and does not bypass it.
- The user disconnects the binding while a retroactive sync is running — the sync stops dispatching new items, in-flight items complete naturally, and a Korean note appears in the History summary explaining the early termination.
- The user replaces the binding (different file key) — historical entries from the previous binding are kept but marked "이전 바인딩"; pending failures from the old binding become non-retryable (their target file no longer applies); the new file starts with empty state until a new sync is triggered.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The Figma 다큐먼트 연동 modal MUST, when a binding is active, expose a primary action labelled "전체 Figma 반영" (or equivalent Korean) that triggers a project-wide retroactive sync. The control MUST be hidden or disabled with an explanatory Korean message when no binding exists or the binding is in `disconnected` / `unreachable` state.
- **FR-002**: The retroactive sync MUST cover both layers: (a) ensure every storyboard has a corresponding Figma page (same logic as 016 FR-006), and (b) for every UI node currently in the project, ensure it is `figma-bound` — generating a Figma-mode design (same logic as 016 FR-010) for any UI node that lacks one, and pushing existing populated sceneGraphs (regardless of original mode) as frames into the correct page.
- **FR-003**: When retroactive sync encounters a UI node with an existing scene graph from any prior generation (HTML or otherwise), it MUST overwrite without showing the per-node prompt from 016 FR-012. The overwrite event MUST be recorded in the binding history with the prior source (e.g., `html` → `figma-bound`).
- **FR-004**: Retroactive sync MUST be idempotent: re-running it when everything is already synced MUST result in zero new pages created, zero new frame creations, and a history entry indicating "변경 없음".
- **FR-005**: While a retroactive sync is running, the modal MUST display live progress (e.g., "storyboards 3/5, UI 17/19"). The action button MUST be disabled to prevent re-entry. A "취소" (Cancel) control MUST be available; pressing it MUST allow in-flight items to complete and stop dispatching new ones (no rollback of completed items).
- **FR-006**: Retroactive sync MUST run under the same concurrency limits as 016 bulk ingestion (per FR-019/FR-021 — batches of up to 10 concurrent UI generations with cooperative cancel boundaries). It MUST NOT bypass these limits.
- **FR-007**: The modal MUST contain a 이력 (History) tab that shows, in reverse-chronological order: (a) each retryable failure as a detailed row with display name, last error (Korean), last attempt timestamp, and a "다시 시도" button; (b) each non-retryable failure as a detailed read-only row with a Korean explanation of why retry is not possible; (c) one-line summary rows for completed sync runs in the form "YYYY-MM-DD HH:MM — [run kind]: 페이지 X건 / 프레임 Y건 성공, Z건 실패".
- **FR-008**: The History tab MUST NOT show every per-item lifecycle event (per-page creation, per-frame push). Successful per-item activity is collapsed into the parent run's summary row.
- **FR-009**: The History tab MUST show a "전체 다시 시도" control at the top of the failure list whenever one or more retryable failures exist for the active binding. Clicking it MUST re-run every retryable failure against the active binding under the same concurrency limits as FR-006.
- **FR-010**: A retry (per-row or 전체 다시 시도) MUST re-run the same logical operation that originally failed. On success, the failure entry MUST be cleared from this view AND from the other surfaces that share its store (ingestion floating panel summary per 016 FR-020-(1) and Inspector Design tab red badge per 016 FR-020-(2)). On re-failure, the row stays with updated last-error and timestamp.
- **FR-011**: The retroactive sync, retry actions, and history view MUST share their failure store with the surfaces created by 016 FR-020. There MUST NOT be a parallel/duplicate failure store.
- **FR-012**: A retryable failure MUST be classified as non-retryable when (a) the binding's target file no longer matches the failure's recorded file key (e.g., the binding was replaced), (b) the underlying storyboard or UI node has been deleted or archived locally, (c) the binding is currently `disconnected`, or (d) the Figma file is no longer reachable in a way that would always fail (e.g., access revoked confirmed by a probe). In each case the row MUST show a Korean explanation and no retry button.
- **FR-013**: The History tab MUST visually distinguish entries originating from the current binding versus entries from a previously replaced binding. Previous-binding entries MUST be grouped under "이전 바인딩" and MUST NOT show retry controls (their target file is no longer the active target).
- **FR-014**: The modal MUST present a clear distinction between "not yet synced" UIs (no attempt was ever made, expected when the architect skipped Figma at ingestion) and "sync failed" UIs (attempt made, error returned). Both states MUST be addressable from this modal — the former is resolved by triggering 전체 Figma 반영, the latter by retrying from the History tab.
- **FR-015**: All retroactive sync runs and retry actions MUST emit the same kind of structured observability events as 016 FR-014 (extended to record the new run kind: `retroactive-sync` and `manual-retry`). No new logging surface is invented.
- **FR-016**: The modal MUST surface a Korean banner / inline message when retroactive sync was triggered while the binding subsequently became unreachable mid-run, including the underlying reason (consistent with 016 FR-015 wording style).
- **FR-017**: Two collaborators on the same project MUST NOT be able to dispatch concurrent retroactive sync runs against the same binding. The system MUST hold a project-scoped lock for the duration of the run; a second collaborator opening the modal during that window MUST see a read-only progress view and an explanatory Korean note that another user is currently syncing.
- **FR-018**: Retry of an individual failure that is already in flight (e.g., another collaborator clicked retry first) MUST be deduplicated — the second click MUST join the in-flight retry rather than dispatch a duplicate Figma request.

### Key Entities

- **FigmaBinding** (existing, from 016): unchanged. This feature consumes its `status` field to gate availability of the new actions.
- **SyncRun**: a single invocation of retroactive sync. Carries `{runId, projectId, bindingId at time of run, kind ∈ {retroactive-sync, manual-retry}, startedAt, finishedAt, summary={pagesCreated, framesPushed, failures}, status ∈ {running, succeeded, partially-succeeded, cancelled, aborted-binding-unreachable}}`. Used to render summary rows in History.
- **SyncFailureEntry** (shared with 016 FR-020 store, extended): `{failureId, projectId, bindingFileKey, target ∈ {storyboard:<id>, ui:<id>}, originalRunId, lastAttemptAt, lastError (Korean), retryability ∈ {retryable, non-retryable, in-flight}, retryReason (only when non-retryable)}`. Surfaced in History tab, ingestion floating panel, and Inspector Design tab — all read from this same store.
- **BindingHistoryEvent** (existing, from 016): unchanged shape; this feature only adds the new event types `retroactive-sync.started`, `retroactive-sync.cancelled`, `retroactive-sync.completed`, `manual-retry.dispatched`, `manual-retry.succeeded`, `manual-retry.failed`, `failure.classified-non-retryable`.
- **ProjectSyncLock**: a project-scoped lock held for the duration of a SyncRun. Records `{projectId, holderUserId, acquiredAt, runId}`. Released at run end (success, failure, cancel, or abort).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For a project with 5 storyboards and 19 UIs all in `html`/no-design state and an active binding, a single 전체 Figma 반영 click results in 5 Figma pages and 19 `figma-bound` UI frames within 120 seconds on a developer laptop with the wireframe service running locally.
- **SC-002**: After the food-delivery sample's bulk ingestion produces simulated Figma push failures (e.g., by throttling the wireframe service), 전체 다시 시도 from the History tab clears ≥95% of those failures on the first click under nominal network conditions.
- **SC-003**: An architect can move from "modal opened" → "retroactive sync started" in ≤2 clicks (open modal → click 전체 Figma 반영).
- **SC-004**: Successful retries from the modal clear the corresponding red badge on the matching UI node's Inspector Design tab in <2 seconds without a page reload (verifying the shared failure store from FR-011).
- **SC-005**: 100% of non-retryable failures are visually distinguishable from retryable ones (different label + no retry button) and carry an explanatory Korean reason.
- **SC-006**: Re-running 전체 Figma 반영 on an already-fully-synced project completes in under 10 seconds, creates zero new Figma pages or frames, and writes a single "변경 없음" history entry.
- **SC-007**: When two users open the same project's modal during a sync run, the second user sees a read-only progress view and an explanatory Korean note in 100% of cases (no duplicate dispatch).

## Assumptions

- The Figma binding and its lifecycle (connect / replace / disconnect / unreachable) are entirely owned by spec 016. This feature is strictly additive to the existing Figma 다큐먼트 연동 modal — it does not change how the binding is established or torn down.
- The existing failure store backing 016 FR-020-(1) (ingestion floating panel) and FR-020-(2) (Inspector Design tab badge) is the canonical source the History tab reads from. No parallel store is introduced.
- "Storyboard" and "UI node" semantics, including the deterministic resolver from UI to storyboard, follow 016 unchanged.
- Concurrency limits for retroactive sync match the 016 bulk-ingestion path (BATCH_SIZE up to 10 concurrent UI generation tasks). The new controller is a wrapper around the same per-item operations 016 already exposes; it does not invent a separate generation pipeline.
- Korean is the user-facing language for all new strings, consistent with the rest of the application.
- "Project-scoped lock" is realised against the shared persistence layer used by Event Modeling collaborative state — the exact mechanism is left to plan/implementation; the spec only requires the observable behaviour from FR-017.
- This feature does not introduce new Figma authentication, permission, or storage paths — it reuses 016's.
- "Generate" inside retroactive sync uses the same generation paths 016 uses on-demand (`Component로 생성` / `OpenPencil AI로 생성`); the choice of generation backend is not redefined here.
- Branch creation (`020-figma-sync-recovery`) is the user's choice; this command does not perform git operations. Spec directory and branch name are independent.
