# Quickstart — 017 Ingestion Token Counter + Granular Suspend (manual smoke)

End-to-end manual verification of US1 + US2. Run after `/speckit-implement` completes its tasks.

## Prerequisites

- Backend running (`uv run uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload`).
- Frontend running (`cd frontend && npm run dev`).
- Neo4j up; `LLM_PROVIDER` / `LLM_MODEL` configured in `.env`.
- An ingestion session is reachable (you can upload via the modal).

## Step 1 — Live token counter (US1)

1. Open `http://localhost:5173/`.
2. Click **문서 업로드** in the top bar.
3. Click **샘플 요구사항 사용** → confirm **분석 시작** (and **삭제하고 계속** if there's existing data).
4. **Expected during the run**:
   - The floating progress panel shows the existing phase / message / percentage as today.
   - Within 2 s of the first phase that calls the LLM (`extracting_user_stories` or `extracting_events`), a token chip appears: e.g. `1.2k tokens`.
   - The chip increments monotonically as phases progress.
   - Hovering / clicking the chip reveals a per-phase breakdown (e.g., `extracting_events: 12.3k`, `extracting_commands: 8.2k`, …).
5. **Expected at completion**:
   - The terminal panel state shows the final cumulative total (e.g. `127k tokens`) plus the breakdown.
   - The total matches the running-total sum visible during the run.
6. **Approximate-marker check**:
   - With a non-OpenAI provider (e.g. `LLM_PROVIDER=google` in `.env`) where `usage_metadata` may be absent, the chip prefixes the value with `~` (e.g. `~127k tokens`) to flag heuristic counting.

## Step 2 — Suspend at LLM call boundary (US2)

1. Start a fresh ingestion (Step 1 above).
2. Wait until the panel shows `extracting_events`, **before progress reaches 50%**.
3. Click the cancel/suspend button in the panel.
4. **Expected**:
   - Within 1 s the chip / status shows `suspending…`.
   - Within 30 s (worst case — one in-flight call must finish; usually much faster) the status flips to `suspended` with the locked-in token total.
   - No new `progress` events for events fire after the `suspended` transition.
5. **Verify in Neo4j** (terminal):
   ```cypher
   MATCH (e:Event) RETURN count(e) AS n
   ```
   Run the same query again 30 s later. The count MUST be identical (FR-010 / SC-006: no new persistence after suspend).
6. **Verify in LLM provider logs** (or equivalent):
   - No LLM API requests with timestamps after the `suspended` transition for this session.

## Step 3 — Suspend during fan-out (FR-008)

`ui_wireframes.py` fans out 10 parallel UI generations per batch. Test that suspend stops new dispatches even mid-batch:

1. Start ingestion in **Figma UI** mode with a `:FigmaBinding` active (so bulk_sync also runs — see spec 016 for setup).
2. Wait until the panel shows `generating_ui` at progress ≥ 87.
3. Click suspend.
4. **Expected**:
   - The current `asyncio.gather` batch's already-in-flight LLM calls finish naturally (we cannot abort them mid-stream).
   - After those return, **no new batch is dispatched**.
   - bulk_sync's per-UI loop, if it had started, also halts at the next `send_and_wait` boundary.
   - Final state: `suspendState=suspended`, with the partial UI count visible in Neo4j and a token total covering only what was actually called.

## Step 4 — Reconnect after suspend

1. Suspend a session (Steps 1–2).
2. Reload the browser (Cmd+R).
3. **Expected**:
   - The session list (or auto-reconnect logic) shows the session as `suspended`.
   - Re-opening the session's status panel shows the locked-in token totals.
   - The ingestion does NOT silently auto-resume.

## Step 5 — Failure modes

- **Token tally fails (tiktoken raises)**: The session's `tokens_approximate` flag flips to `True`, the chip shows a `~` prefix; ingestion does NOT abort.
- **LLM provider does not return `usage_metadata`**: heuristic fallback (`tiktoken` for OpenAI-compatible models, `len(text)/4` otherwise) kicks in; counter still updates within 2 s.
- **Suspend during a 120 s `_render_jsx` call**: status is `suspending` for up to 120 s, then flips to `suspended`. The 30 s SC-004 target applies to the common case (LLM call ~30 s) but not to wireframe-service edge cases. Acceptable.

## Cleanup

- Suspended / completed sessions are auto-cleaned by the existing TTL logic in `ingestion_sessions.py`. No manual cleanup needed for this feature.

## Out of scope (NOT to verify here)

- Cost in dollars (multiplied from token totals) — future feature.
- Cross-session aggregation reporting — future feature.
- Resume of a suspended session — not supported in this feature.
- Mid-stream LLM provider request abort — not supported (provider limitation; FR-005 acknowledges).
