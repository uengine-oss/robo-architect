# SSE Contract Additions — 017 Ingestion Token Counter + Granular Suspend

This document specifies the additive changes to the existing
`GET /api/ingest/stream/{session_id}` SSE channel. No new event types are
introduced; existing `progress` events gain two optional fields.

## Stream

```
GET /api/ingest/stream/{session_id}
Accept: text/event-stream
```

Unchanged from current behavior. SSE frames keep the existing format:

```
event: progress
data: {"phase":"...","message":"...","progress":N,"data":{...}}
```

## `progress` event — extended payload

### Schema (added fields)

```jsonc
{
  "phase": "extracting_events",        // unchanged: IngestionPhase value
  "message": "...",                    // unchanged
  "progress": 36,                      // unchanged: 0..100
  "data": { /* unchanged */ },

  // ── NEW (017) ──
  "tokens": {
    "total": 12345,                    // required when present; cumulative session total
    "byPhase": {                       // optional; included only when a phase delta exists
      "extracting_events": 12345
    },
    "approximate": false,              // optional; True if any call was heuristic-counted
    "lastCallTokens": 1234             // optional; tokens used by the most recent call
  },
  "suspendState": "running"            // NEW (017); "running" | "suspending" | "suspended"
}
```

### Field semantics

- **`tokens.total`** — session cumulative; monotonically non-decreasing across the run. Frontend MUST treat any absence of `tokens` as "no update; keep showing previous value." A reset to 0 only happens when a new SSE stream for a different session_id is opened.
- **`tokens.byPhase`** — sparse. Frontend merges into a local map (later keys win). Phases not present in this event keep their previous value.
- **`tokens.approximate`** — sticky. Once True for a session, it stays True (any subsequent exact tally cannot retroactively make the total exact).
- **`tokens.lastCallTokens`** — non-cumulative; just the most recent call's contribution. Useful for "this call cost N" display; absence in an event means "no LLM call returned in the interval since the previous event."
- **`suspendState`** — emitted on every `progress` event so a reconnect immediately surfaces the latest state without history replay.

### When the backend emits the `tokens` block

1. On every existing `progress` event after the first LLM call returns (token block reflects the running totals).
2. On a synthetic `progress` event emitted by the token-tally callback if no other `progress` event would fire within 2 s of an LLM call's completion. The synthetic event has the same `phase` / `message` / `progress` as the previous event (no apparent phase change to the user) — only the `tokens` block updates.
3. On the terminal `progress` event with `phase=COMPLETE` or `phase=ERROR` — the locked-in final totals.

### When the backend emits `suspendState`

On every `progress` event. State transitions:

- `running`: default while `session.is_cancelled == False`.
- `suspending`: set by `POST /api/ingest/{session_id}/cancel` immediately. The next `progress` event after the cancel call carries `suspendState="suspending"`.
- `suspended`: set when the workflow's outer `_run()` catches `CancelledError` from the suspend gate (i.e., the workflow has fully exited). Emitted with a final `progress` event whose `phase=ERROR` and `data.cancelled=true` (existing behavior) — `suspendState="suspended"` is the new field on that same event.

## Backwards compatibility

Clients that do not read `tokens` or `suspendState` see no change. The added fields are pure additions to the JSON payload; no existing fields are removed or renamed.

## Example — full lifecycle

### 1. First `progress` after upload (no LLM calls yet)

```
event: progress
data: {"phase":"parsing","message":"문서 파싱 중...","progress":5,"data":{},"suspendState":"running"}
```

(no `tokens` block — no LLM call has completed yet)

### 2. First `progress` after the parsing LLM call returns

```
event: progress
data: {"phase":"parsing","message":"파싱 완료","progress":10,"data":{},
       "tokens":{"total":1234,"byPhase":{"parsing":1234},"approximate":false,"lastCallTokens":1234},
       "suspendState":"running"}
```

### 3. Mid-run, user clicks 취소

```
event: progress
data: {"phase":"extracting_events","message":"...","progress":36,"data":{...},
       "tokens":{"total":12345,"byPhase":{"parsing":1234,"extracting_events":11111},
                 "approximate":false,"lastCallTokens":2222},
       "suspendState":"suspending"}
```

### 4. After the in-flight call returns and the gate raises CancelledError

```
event: progress
data: {"phase":"error","message":"❌ 생성이 중단되었습니다","progress":36,
       "data":{"error":"Cancelled by user","cancelled":true},
       "tokens":{"total":13567,"approximate":false},
       "suspendState":"suspended"}
```

The token total includes the in-flight call that returned (its tokens were already paid for; we count them honestly).
