# Quickstart — Figma Sync Recovery & Retroactive Push

Manual end-to-end smoke for spec 020. Assumes the 016 quickstart already passes (binding can be created, plugin connects, fonts load, ingestion in figma mode produces sceneGraphs). Run from the repo root.

## Prerequisites

- Backend running: `uv run uvicorn api.main:app --reload --port 8000`
- Frontend running: `cd frontend && npm run dev` (default port 5173)
- Wireframe service running: `cd open-pencil/packages/cli && bun run wireframe-service`
- Figma desktop open with the plugin connected (per 016 quickstart)
- A test Figma file you can write to; copy its file key (the `b7085rfvcgkBeIkljMNc8y`-style segment from the URL)

Reset the project state (one Event Modeling project, with at least one storyboard and a few UIs) before each scenario.

## Scenario 1 — First-time retroactive sync (US1 happy path)

**Setup**: ingest the food-delivery sample with `Figma UI` mode **OFF** (HTML mode). Confirm in Neo4j: `MATCH (u:UI) RETURN count(u), count(u.figmaSyncStatus)` — every UI exists, none have `figmaSyncStatus`.

**Steps**:

1. Open the app at `http://localhost:5173`.
2. Click the **Figma** button in the top bar. The 다큐먼트 연동 modal opens on the **연결 상태** tab.
3. Confirm the binding header shows `상태: 활성` and the file name from your test Figma file.
4. Click the new **전체 Figma 반영** button.
5. Confirm a confirmation dialog appears: "기존 sceneGraph 가 있으면 덮어씌워집니다. 계속하시겠습니까?". Click 계속.
6. Watch the progress section update: "storyboards 0/5 → 5/5", then "UI 0/19 → 19/19".
7. When the run completes, the section flips to "완료 — 페이지 5건 / 프레임 19건 성공" with no failures.
8. Switch to the Figma desktop. Confirm the linked file now contains 5 pages (one per storyboard) and 19 frames distributed across them.
9. In the app, open the **이력** tab. Confirm one summary row appears: "2026-05-08 ... — 전체 동기화: 페이지 5건 / 프레임 19건 성공".
10. Open Inspector on any UI node. Confirm the Design tab shows the linked Figma frame (no red badge).

**Pass criteria**: total wall-clock under 120 s on a developer laptop (SC-001); 5 pages + 19 frames in Figma; no red badges anywhere; one summary row in History.

## Scenario 2 — Idempotent re-run (FR-004 / SC-006)

**Setup**: scenario 1 just ran successfully.

**Steps**:

1. Without changing anything, click **전체 Figma 반영** again. Confirm the dialog. Click 계속.
2. The progress shows "storyboards 5/5" almost immediately (no creates) and "UI 19/19" — but each UI is `pagesAlreadyOk` / no overwrite needed.
3. The completion banner reads "변경 없음".
4. Refresh the modal. The 이력 tab shows the new run as "전체 동기화: 변경 없음".

**Pass criteria**: completes in <10 s; zero new Figma pages or frames; "변경 없음" banner; new summary row marked accordingly.

## Scenario 3 — Retry from History tab (US2 happy path)

**Setup**: ingest the food-delivery sample with `Figma UI` mode **ON** but throttle the wireframe service to force ~3 push failures (e.g., temporarily kill `wireframe-service` after 2/3 of UIs are pushed). Confirm 3 `:UI` nodes have `figmaSyncStatus='failed'`. Restore the wireframe service.

**Steps**:

1. Open the modal → **이력** tab.
2. Confirm the failure list at the top shows 3 rows: each with the UI display name, last Korean error, and a 다시 시도 button. A header **전체 다시 시도** button is visible.
3. Open Inspector for one of the failed UIs in another tab — confirm the red **Figma 동기화 실패** badge is showing on the Design tab.
4. Back in the modal, click **전체 다시 시도**.
5. Watch the row-level state change to "재시도 중..." and then disappear as each succeeds.
6. After all 3 succeed, the list is empty and a single new summary row appears below: "전체 다시 시도: 프레임 3건 성공".
7. Switch back to the Inspector tab — the red badge has cleared without a refresh (SC-004).

**Pass criteria**: all 3 failures cleared on first click (SC-002); Inspector badge clears within 2 s without page reload; one summary row added.

## Scenario 4 — Concurrent run lock (FR-017)

**Setup**: a project ready for retroactive sync (any state where 전체 Figma 반영 would dispatch). Two browser windows on `http://localhost:5173`, both with the modal open.

**Steps**:

1. In window A, click **전체 Figma 반영** and confirm.
2. While window A is mid-run, in window B click **전체 Figma 반영**.
3. Window B receives a 409 and the UI flips to a read-only progress view: "다른 사용자가 동기화 중입니다 — by <actor>". The 전체 Figma 반영 button is disabled.
4. Window B's progress bar mirrors window A's progress in real time (it is subscribed to the same SSE stream).
5. When window A's run completes, window B's view flips to the completion banner; window B's button re-enables.

**Pass criteria**: only one run dispatch reaches the orchestrator; window B never produces a 2nd `runId`; both windows see the same progress.

## Scenario 5 — Cancel mid-run (FR-013 / FR-005)

**Setup**: same as scenario 1 but ingest a larger project (50+ UIs) so cancellation is easy to time.

**Steps**:

1. Click **전체 Figma 반영**. Wait until the progress shows "UI 8/50".
2. Click 취소.
3. Watch the run finish in-flight items (UI 9, 10 — whichever were dispatched in the current batch) and stop without dispatching the next batch.
4. The completion banner reads "취소됨 — 프레임 N건 성공" where N is the count actually dispatched.
5. Open the **이력** tab. The new summary row's status is `cancelled`.
6. Confirm UIs that were never dispatched still have `figmaSyncStatus = null` (not `'failed'`) — they remain in "not yet synced" state and can be picked up by a future trigger.

**Pass criteria**: in-flight items complete; not-yet-attempted UIs remain `null`; summary row shows `cancelled`.

## Scenario 6 — Disconnected binding shows read-only history (FR-011)

**Setup**: scenario 1 just ran successfully. Then click 연결 해제 in the **연결 상태** tab to disconnect.

**Steps**:

1. Reopen the modal. The 연결 상태 tab now shows the Connect form (no binding).
2. Switch to the **이력** tab. The history rows from the disconnected binding are visible but rendered read-only.
3. Hover over the disabled 다시 시도 buttons. The tooltip reads "binding 해제됨".
4. Reconnect to the same Figma file (same file key) via the **연결** tab.
5. Switch back to **이력** — retry buttons are re-enabled because the failure rows' `bindingFileKey` matches the new active binding's file key.

**Pass criteria**: retry buttons disabled while disconnected; re-enabled after reconnecting to the same file.

## Scenario 7 — Replace binding marks old failures non-retryable (FR-012 / FR-013)

**Setup**: scenario 3 just produced 3 failures (none retried yet).

**Steps**:

1. In the **교체** tab, paste a *different* Figma file's URL. Click 교체.
2. Switch to **이력**. Failures from the previous binding now appear under a "이전 바인딩" group (collapsed by default).
3. Expand the group. The retry buttons are gone; each row shows "재시도 불가 — 이전 바인딩".
4. Hover the badge for the explanatory tooltip.

**Pass criteria**: previous-binding failures grouped, no retry buttons, Korean reason visible (FR-013, SC-005).

## Scenario 8 — In-flight retry dedupe (research D3)

**Setup**: scenario 3's 3 failures still present.

**Steps**:

1. In window A, click 다시 시도 on UI #1.
2. Within ~50 ms in window B, click 다시 시도 on the same UI #1.
3. Inspect backend logs. Look for `figma_binding.retry.deduped` event for UI #1.
4. Both windows should receive the *same* eventual outcome (success or failure event) — only one Figma plugin dispatch occurs.

**Pass criteria**: exactly one `CREATE_FRAME_IN_PAGE` is sent to the plugin (verifiable via plugin debug logs); both windows reflect the resulting `figmaSyncStatus`.

---

## Constitution & spec coverage

| Item | Where exercised |
|---|---|
| Constitution III (Streaming) | Scenarios 1, 4 (SSE progress) |
| Constitution IV (Human-in-the-loop) | Scenario 1 step 5 (confirmation dialog) |
| Constitution VII (Observable) | Scenario 8 (correlation-tagged dedupe events in backend logs) |
| FR-001 / FR-002 / SC-001 | Scenario 1 |
| FR-003 / FR-014 (overwrite without per-node prompt) | Scenario 1 step 5 dialog (single bulk-style confirm, no per-UI prompt) |
| FR-004 / SC-006 | Scenario 2 |
| FR-005 / FR-013 cancel semantics | Scenario 5 |
| FR-007 / FR-008 (history granularity) | Scenarios 1, 2, 3 (one row per run, no per-item rows) |
| FR-009 / FR-010 / SC-002 / SC-004 | Scenario 3 |
| FR-011 | Scenario 6 |
| FR-012 / FR-013 / SC-005 | Scenario 7 |
| FR-017 / SC-007 | Scenario 4 |
| FR-018 (dedupe) | Scenario 8 |
