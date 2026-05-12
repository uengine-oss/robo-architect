# Data Model — 017 Ingestion Token Counter + Granular Suspend (Phase 1)

This feature adds **only transient session state** — no Neo4j schema changes, no new persisted entities. The model below documents the in-memory shapes and the SSE additions.

## In-memory: `IngestionSession` deltas

Existing class `IngestionSession` (in `api/features/ingestion/ingestion_sessions.py`) gains four fields. All start at zero / empty on session creation, are mutated only by the token-tally callback and the suspend handler, and are reset on a fresh ingestion (already handled — sessions are recreated per upload).

| Field | Type | Lifecycle | Purpose |
|---|---|---|---|
| `tokens_total` | int | accumulated across the run | session-level total across all LLM calls |
| `tokens_by_phase` | dict[str, int] | append-on-call | per-phase aggregation; key is `IngestionPhase` value (e.g. `"extracting_events"`) |
| `tokens_approximate` | bool | sticky once True | True if at least one call was tokenized via the heuristic fallback (D2). Drives the `~` prefix in the UI. |
| `tokens_last_call` | int \| None | overwritten per call | tokens used by the most recent LLM call, for the SSE diff display |
| `suspend_state` | `"running" \| "suspending" \| "suspended"` | state machine | UI status. Transitions: running → suspending (on user click) → suspended (after in-flight call returns). |

The existing `is_cancelled: bool` and `is_paused: bool` fields stay; `suspend_state` is a derived display field maintained by the suspend handler so the UI doesn't have to combine multiple booleans.

### `TokenUsage` (per-call record, optional ledger)

The per-call records that feed `tokens_by_phase` are produced by the callback but **not stored** on the session by default — only the aggregates above are kept. A debug toggle (`SmartLogger` category `ingestion.tokens.call`) emits each call's `TokenUsage` to logs for forensics:

```python
@dataclass
class TokenUsage:
    phase: str           # IngestionPhase value at the time of the call
    model: str           # e.g., "gpt-4.1-2025-04-14"
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int    # prompt + completion
    approximate: bool    # True if from tiktoken fallback / heuristic
    at: datetime         # call-end timestamp
```

This shape never crosses the network and never persists; it lives just long enough to be aggregated into the session fields and logged.

## SSE event payload extension

The existing `progress` event on `/api/ingest/stream/{session_id}` gains an optional `tokens` block. Every existing field is unchanged; clients that don't read `tokens` simply ignore it.

```jsonc
{
  "phase": "extracting_events",
  "message": "...",
  "progress": 36,
  "data": { /* unchanged per-event payload */ },

  // NEW (this feature):
  "tokens": {
    "total": 12345,                     // session-level cumulative total
    "byPhase": {                        // optional, included when changed
      "extracting_events": 12345
    },
    "approximate": false,               // True if any tally was heuristic
    "lastCallTokens": 1234              // tokens used by the most recent call
  },

  // NEW (this feature):
  "suspendState": "running"             // "running" | "suspending" | "suspended"
}
```

The `tokens.byPhase` block is included only when a phase's value changes from the previous event (saves SSE bytes). Frontend reconciles by merging incoming `byPhase` into a local cache.

`suspendState` is included on every event so a reconnect immediately surfaces the latest state.

## State machine: suspend lifecycle

```text
running ──user clicks 취소──▶ suspending ──in-flight call returns──▶ suspended
   │                              │
   │                              └── (no in-flight call) ────▶ suspended (within 5 s)
   │
   └── (workflow completes naturally) ────▶ COMPLETE / ERROR
```

- `running`: default. `is_cancelled=False`.
- `suspending`: set by the cancel endpoint immediately on click. `is_cancelled=True` is the trigger flag for the suspend gate; `suspend_state="suspending"` is the user-visible label.
- `suspended`: set by the workflow `_run()`'s `except CancelledError` handler when the workflow exits cleanly through the gate, or by the gate itself when the next call boundary is reached without an in-flight call. Emits a final `progress` event with `phase=ERROR` and `data.cancelled=True` (existing behavior) plus the locked-in `tokens` block.

## What does NOT change

- No new Neo4j labels, properties, or constraints.
- No new REST endpoints.
- No new SSE event types (only field additions).
- No changes to the `IngestionPhase` enum.
- No changes to provider configuration (`LLM_PROVIDER`, `LLM_MODEL`, etc.).
