# Research: Ingestion Token Counter + Granular Suspend (Phase 0)

## D1 — How to capture token usage uniformly across providers

**Decision**: Use a LangChain `BaseCallbackHandler` whose `on_llm_end(response, ...)` reads `AIMessage.usage_metadata` (LangChain v0.2+ standardized field). Bind one callback per `IngestionSession` in `ingestion_llm_runtime.get_llm()` so every chat model produced for that session reports back to the session's tally automatically.

**Rationale**:
- `usage_metadata` is populated by LangChain's `langchain-openai`, `langchain-anthropic`, `langchain-google-genai`, and the OpenRouter adapter — exactly the providers the project supports per Constitution VI. Capturing here gives a single integration point, no provider-specific code in features.
- A callback is non-invasive: features keep calling `llm.invoke(...)` / `llm.ainvoke(...)` / `asyncio.to_thread(llm.invoke, ...)` exactly as today. The callback fires on every successful response.
- Failure semantics: if `usage_metadata` is missing (older provider, custom backend), the callback uses `tiktoken` to count the prompt tokens locally and the completion tokens via `tiktoken` on the response text. The result is flagged `approximate=True` so the UI can show a `~` prefix.

**Alternatives considered**:
- *Per-feature manual counting*: rejected. Every phase already calls the LLM differently (sync `invoke` vs async `ainvoke` vs `bind_tools` agent loops). Counting per call site means dozens of edits and high drift risk.
- *Patching `get_llm()` to wrap every chat model*: callback approach is the same patch site but without monkey-patching internals. LangChain callbacks are the supported extension point.
- *Reading provider HTTP responses directly via httpx middleware*: rejected. Coupled to provider HTTP shape and bypasses LangChain abstraction.

## D2 — Tokenizer fallback when usage_metadata is absent

**Decision**: Add `tiktoken` (already in many Python LLM stacks; ~2 MB) as a *fallback* dependency. For OpenAI models we use `tiktoken.encoding_for_model(model_name)`; for Anthropic / Google we ship a single `cl100k_base` heuristic encode (close enough — within ~10% empirically and clearly marked as approximate); for unknown models we fall back to `len(text) / 4` (a known industry heuristic).

**Rationale**:
- The primary path uses provider-reported counts (D1), so the fallback runs rarely. Optimizing it is unnecessary.
- Embedding tiktoken in the wheel adds ~2 MB; acceptable.
- All non-exact paths flag `approximate=True` so the UI can show a `~` prefix (per FR-002 "best-effort" wording in spec).

**Alternatives considered**:
- *Use Anthropic's `count_tokens` SDK*: extra dependency, blocking call, and Anthropic actually populates `usage_metadata` on `ChatAnthropic`, so this is unnecessary.
- *Always use `len(text) / 4`*: too inaccurate for OpenAI which has a well-known tokenizer. Loses user trust in the counter.

## D3 — Where to put the suspend gate

**Decision**: A central context manager `async with session_call_slot(session):` that:
1. Awaits a microtask to give the cancel handler a chance to run.
2. Raises `asyncio.CancelledError` (caught by the workflow's outer `except CancelledError` handler — already present in `_run()` in `router.py`) if `session.is_cancelled` is set.
3. Yields control to the wrapped LLM/wireframe call.

Every LLM call site in every phase wraps the call in this context manager. Inside the FR-017 retry stack (`_render_jsx` retries, agent loop, wrapper retry), each retry attempt also wraps. Inside `asyncio.gather(*tasks)` fan-outs (e.g., `ui_wireframes.py` BATCH_SIZE=10), each individual task uses the same context manager so the *first* check happens before any LLM dispatch.

**Rationale**:
- Single point of truth for the cancel check. No phase-by-phase ad-hoc `if session.is_cancelled: return`.
- `CancelledError` propagates naturally up `await` chains — the existing workflow's `except CancelledError` already emits the suspended event.
- The context manager pattern also gives a hook for future enhancements (rate limiting, audit logs) without re-touching every call site.

**Alternatives considered**:
- *Cancel via `task.cancel()` on the workflow_task*: rejected. Cancelling Python coroutines mid-await is brittle (many libraries don't propagate `CancelledError` cleanly), and we still need to wait for the in-flight LLM call to return before declaring "suspended" anyway. Cooperative cancellation at well-defined boundaries is more robust.
- *Per-LLM-call cancellation token passed to provider*: most providers don't support mid-stream cancellation. The provider HTTP request would need to be aborted client-side, which can leave the provider's account in a charged-but-incomplete state and complicates retries. Letting the in-flight call finish is the spec's contract (FR-005, "in-flight may complete; results MUST NOT trigger further calls").

## D4 — How to surface token totals to the frontend

**Decision**: Extend the existing `progress` SSE event payload with an optional `tokens` block:

```json
{
  "phase": "extracting_events",
  "message": "...",
  "progress": 36,
  "data": { ... existing per-event data ... },
  "tokens": {
    "total": 12345,
    "byPhase": { "extracting_events": 12345 },
    "approximate": false,
    "lastCallTokens": 1234
  }
}
```

The `tokens` block is emitted on (a) every existing progress event after the first LLM call returns (so the counter ticks up with normal phase events) and (b) a synthetic micro-event after each LLM call's token tally completes if no progress event would otherwise fire within 2 s. This satisfies FR-002's "within 2 s of every subsequent call's completion."

**Rationale**:
- Reuses the existing event type — no new SSE handler in the frontend needed; just a new field to read from `event.data`.
- Backwards compatible: clients that don't read `tokens` simply ignore it.
- `byPhase` enables the per-phase breakdown (FR-003) without a separate request.

**Alternatives considered**:
- *Separate `tokens` SSE event type*: more complex frontend wiring; chose to piggyback on `progress`.
- *Frontend re-counts via `tiktoken` in browser*: doubles tokenizer cost, and prompts are server-only — frontend would have to reverse-engineer prompts. Rejected.

## D5 — Persistence of the token ledger

**Decision**: Transient. Token totals live on the in-memory `IngestionSession` for the lifetime of that session (typically minutes; until the SSE channel disconnects or the session is cleaned up after `phase=COMPLETE/ERROR`). On suspend, the totals stay attached to the session so the panel still shows them. Once the session is cleaned up, totals are gone.

**Rationale**:
- The user's stated need is "see while running, see at end." Cross-session aggregation ("how much did I spend this week") is a future feature, not in this spec.
- Persisting to Neo4j would require a new label and either denormalize per-call rows (data volume) or aggregate per-run (loss of detail). Both have non-trivial cost for a feature that may not need them.
- If cross-session reporting becomes a need, a future spec adds an `:IngestionRun` node with `tokensTotal` + `byPhase` JSON. That's strictly additive on top of this design.

**Alternatives considered**:
- *Append-only run log file on disk*: useful for ops but bypasses SmartLogger conventions; if needed, add to SmartLogger event payloads (`ingestion.tokens.run_done` carries the full breakdown) and tail logs. No new persistence layer.

## Cross-cutting: interaction with FR-017 retry stack

The retry stack from spec 016 issues *the same JSX* up to 3× through `_render_jsx`, plus the agent loop fallback, plus the wrapper retry. Without a suspend gate, a suspended session can keep retrying for up to ~24 minutes worst case (3 transport × 3 wrapper × 8 agent steps × ~120 s timeout). With the gate placed before each retry, the first check fires within 5 s of the suspend ack and the chain exits cleanly.

The gate does NOT shorten any *single* in-flight call — that's by design (FR-005). It only stops *new* calls. So the worst-case suspend latency stays at "longest single LLM/render call timeout" which is 120 s for `_render_jsx` and ~60 s for typical LLM phase calls. The 30 s SC-004 target is reachable in the common case where the in-flight call returns quickly.

## Cross-cutting: interaction with bulk_sync (016 FR-019b)

`bulk_sync.sync_batch` already runs after each `asyncio.gather` batch. Its per-UI loop has a natural cancel point (top of each iteration), and its inner `_ensure_page_for_command` / `push_frame_for_ui` calls each translate to a `send_and_wait` plugin transport request. The gate sits in front of the `send_and_wait`, so suspend stops further plugin requests and the `figmaSyncStatus='failed'` state from FR-020 covers the partial result naturally (the UI just shows up in the FR-020 retry list later).
