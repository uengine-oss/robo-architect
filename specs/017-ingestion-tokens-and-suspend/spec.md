# Feature Specification: Ingestion Token Counter + Granular Suspend

**Feature Branch**: `017-ingestion-tokens-and-suspend`
**Created**: 2026-05-07
**Status**: Draft
**Input**: User description: "문서 업로드에서 생성 과정에서 스테이터스 팝업에 사용된 토큰 수도 카운트에서 보여주는 기능을 좀 만들어 주면 좋겠어 토큰수 틱토큰을 이용하던지 해가지고 그리고 지금 중간에 서스펜드를 했을 때 그대로 멈추지를 않고 계속 진행이 되고 있는데 아마 어떤 구간에서 멈추는지를 모르겠으나 각 LLM 호출 히트 한 건 당 무조건 서스펜드가 가능해야 돼 예를 들어서 이벤트를 생성 중에 아까 서스펜드를 했는데도 계속 다른 이벤트들을 계속 추출하고 있더라고 그거는 멈췄어야 하는 거야"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Live token usage visibility during ingestion (Priority: P1)

When the architect uploads a requirements document and the analysis runs, the floating status panel shows — alongside the current phase, message, and progress percentage — a running count of LLM tokens consumed so far in this ingestion session. The count updates as each phase advances and each individual LLM call returns, so the architect can see cost accumulating in real time and tell whether a particular phase is unusually expensive. After completion, the final total is preserved on the summary line.

**Why this priority**: Token spend on a single ingestion can range from thousands to hundreds of thousands depending on document size and model. Without visibility, the architect has no way to budget runs, compare cost between providers, or notice a runaway phase before it bills. This is a small UI addition with high operational payoff.

**Independent Test**: Upload the built-in food-delivery sample and watch the status panel as the run progresses. Verify (a) a token counter is visible from the first phase onward, (b) it monotonically increases as the run progresses (never decreases or resets between phases), (c) the displayed total at the end is within 5% of an externally-counted ground truth (e.g., the same prompts re-tokenized by the user with a known tokenizer offline).

**Acceptance Scenarios**:

1. **Given** an ingestion is running, **When** the first LLM call returns, **Then** the status panel's token counter increments from 0 to the call's prompt+completion token count within 2 seconds of that call's completion.
2. **Given** ingestion has run through several phases, **When** the architect looks at the status panel, **Then** they see a single cumulative token total for the session (not just the current phase) plus a breakdown by phase available on hover or expand.
3. **Given** ingestion completes successfully, **When** the architect dismisses the status panel, **Then** the final token total is preserved in the session's summary view (alongside elapsed time and node counts).
4. **Given** ingestion errors out mid-run, **When** the failure is shown, **Then** the partial token count up to the failure is still displayed (the architect needs to know how much was spent before the abort).

---

### User Story 2 - Suspend stops at the next LLM call boundary (Priority: P1)

When the architect clicks the suspend (cancel) button while ingestion is running, the workflow MUST stop before issuing the next LLM call — not after the whole current phase finishes, and not after a remaining batch completes. Specifically, if the architect suspends partway through event extraction, no more events are extracted; the run halts at whichever LLM call was in flight or about to start, and the panel reflects "suspended" within seconds.

**Why this priority**: The architect's primary reason to suspend is "this is going wrong, stop spending money / stop polluting the graph." A suspend that takes another minute (or longer) to honor — extracting events the architect explicitly asked not to extract — defeats the point and erodes trust in the whole tool. Granular cancellation is a baseline expectation for any long-running job UI.

**Independent Test**: Start an ingestion of a document long enough to extract ≥ 20 events. As soon as the panel shows the first event being extracted, click suspend. Verify (a) within 30 seconds the panel reads "suspended", (b) the total event count saved in Neo4j after suspend is at most 1 greater than what was visible at the moment of clicking suspend (i.e., the in-flight call may finish but no new ones start), (c) re-running ingestion does not crash on partial state.

**Acceptance Scenarios**:

1. **Given** ingestion is mid-LLM-call (e.g., extracting events), **When** the architect clicks suspend, **Then** the in-flight call is allowed to finish (its results may or may not be persisted — see Edge Cases) but no further LLM calls in the batch or phase are issued.
2. **Given** ingestion is between LLM calls (waiting on a wireframe service or other I/O), **When** the architect clicks suspend, **Then** the workflow halts immediately at that boundary — within 5 seconds of the click — without dispatching the next LLM call.
3. **Given** the architect suspends and then resumes (or starts a new ingestion), **When** the run continues/restarts, **Then** the previously suspended session shows a clear "suspended" status in the session list and is not silently re-started.
4. **Given** a phase fans out N parallel LLM calls (e.g., per-aggregate property generation, per-UI wireframe generation), **When** the architect suspends, **Then** none of the not-yet-started calls in that fan-out are dispatched; calls already in flight either complete or are aborted (consistent across phases — see FR-008).

---

### Edge Cases

- A long single LLM call (60+ s) is in flight when suspend is clicked. The call cannot be cancelled mid-stream by the LLM provider — the system MUST wait for it to return, but MUST NOT use its result to trigger downstream work. The architect sees "suspending..." until the call returns, then "suspended". The result of that one call MAY be persisted to Neo4j to avoid losing partial work, as long as nothing further is triggered from it.
- The user clicks suspend twice. The second click MUST be a no-op; the panel shows "suspended" or "suspending..." either way.
- A suspended session is later resumed (if resume is supported). Token counter MUST resume from where it left off, not reset. (If resume is not supported, this edge case does not apply.)
- An LLM provider returns an error mid-call (rate limit / 5xx). The retry stack from FR-017 (016) takes over — but each retry attempt MUST also be subject to the suspend check, so a suspended session does not keep retrying.
- The wireframe service (Bun, port 7610) is the next call when the architect suspends. The system halts at that boundary too — wireframe-service calls are treated as "LLM-equivalent" expensive calls for cancellation purposes, even though they don't burn LLM tokens.
- Token counting fails (e.g., tiktoken can't tokenize a particular Unicode sequence, or the model's tokenizer is unknown). The counter shows a best-effort estimate and a small warning indicator; ingestion does not abort over a counting failure.
- The architect uploads a giant document with millions of expected tokens. The counter MUST keep rendering even at high values (e.g., format with k/M suffix above 10 000 / 1 000 000) and never freeze the UI.
- A session was suspended on the previous page load. On reconnect, the SSE stream MUST report "suspended" and the panel MUST NOT auto-resume.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST count input (prompt) and output (completion) tokens for every LLM call made during an ingestion session and aggregate the totals at the session level.
- **FR-002**: System MUST surface the running session-level total in the existing ingestion status panel as soon as the first LLM call completes, and update the displayed value within 2 seconds of every subsequent call's completion.
- **FR-003**: System MUST also expose a per-phase breakdown (e.g., "extracting events: 12 345 tokens", "extracting commands: 8 211 tokens") accessible from the same status panel without navigating away.
- **FR-004**: Token counts MUST be retained on the session's summary view (post-completion) so the architect can review them after the panel auto-collapses, and MUST be retained on error/suspend so the architect can see "spent so far" even on incomplete runs.
- **FR-005**: System MUST honor a suspend request at every LLM call boundary, not only at phase boundaries. A suspend issued while a phase is dispatching N concurrent LLM calls MUST stop new calls from being dispatched — already-in-flight calls may complete (a single in-flight call cannot be cancelled mid-stream by most providers) but their results MUST NOT trigger any further LLM calls in the same session.
- **FR-006**: System MUST honor the suspend request within 30 seconds of the click in the worst case (a single long in-flight call finishing) and within 5 seconds in the common case (no LLM call in flight). The status panel MUST visibly reflect "suspending" during the wait and "suspended" once the workflow has fully halted.
- **FR-007**: Suspend MUST also gate every retry inside the existing reliability retry stacks (transport-level, agent fallback, wrapper retry — see spec 016 FR-017). A suspended session MUST NOT keep retrying after suspend.
- **FR-008**: Calls into the wireframe rendering service (the JSX→sceneGraph path used by `Figma UI` mode and per-node Design tab generation) MUST be treated as suspendable boundaries equivalent to LLM calls — not because they cost tokens, but because they are the dominant non-LLM long-running calls and the architect's "stop now" intent applies equally.
- **FR-009**: When suspend is acknowledged, the session's status MUST be persisted as `suspended` (or equivalent) so that a page reload, server restart, or reconnect surfaces the suspended state rather than silently re-starting.
- **FR-010**: The system MUST NOT lose previously persisted Neo4j work on suspend; only future work is cancelled. The architect's expectation is "stop here, keep what you've got."

### Key Entities

- **IngestionSession** (existing): gains a session-level `tokensUsed` aggregate (total prompt + completion across the run) and a per-phase breakdown map. The cancellation flag (already present) is the same flag, but its check granularity is tightened by FR-005.
- **TokenLedger** (conceptual, may live on the session): per-LLM-call records `{phase, callIndex, model, promptTokens, completionTokens, at}` so the breakdown by phase and over time is reconstructable.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A token counter is visible in the floating status panel from the first LLM call onward, in 100% of ingestion sessions across all input sources (file upload / text input / Jira / Figma / analyzer-graph).
- **SC-002**: The displayed cumulative token total at session end is within 5% of an externally-counted ground truth across a sample of 5 representative documents (small / medium / large / Korean / English-mixed).
- **SC-003**: Token counter updates appear within 2 seconds of each LLM call's completion in 95% of cases under normal network conditions.
- **SC-004**: Suspend is acknowledged with a "suspended" panel status within 30 seconds in 100% of attempts and within 5 seconds when no LLM call is in flight at click time.
- **SC-005**: Suspending mid-phase results in zero new LLM calls being issued after the suspend acknowledgement. Measured by inspecting the LLM provider's request log: no requests with timestamps after the suspend ack moment for the suspended session's identifier.
- **SC-006**: A suspended session's Neo4j footprint at the time of suspend equals its footprint 30 seconds later (i.e., no work continues to be persisted). Measured by snapshotting `count(node)` per label immediately after the suspend ack and again at +30 s.
- **SC-007**: Resuming or re-running ingestion after a suspend has zero crash rate from corrupted partial state across 10 sequential runs.

## Assumptions

- The token counter is best-effort approximate. We will use a model-appropriate tokenizer (e.g., `tiktoken` for OpenAI models, the upstream tokenizer for Anthropic/Google/OpenRouter where available, and a character-based heuristic with a clearly-marked `~` prefix when no exact tokenizer is available). The user will treat the value as a budgeting aid, not a billing-exact figure.
- Cost-in-currency display is **out of scope for this feature** — only raw token counts. A future feature can multiply by a per-model price table.
- Suspend semantics here apply specifically to ingestion (`/api/ingest/*` flow). The 016 figma-binding bulk_sync sub-step counts as part of the ingestion (it's chained from the same workflow), so its retries are also gated by the same suspend flag.
- We assume one suspend mechanism — the user's existing button. We do not introduce per-phase pause/resume granularity; suspend is terminal.
- The retry stack from spec 016 FR-017 (transport-level / agent / wrapper) stays in place; this feature only adds a cancellation check between retry attempts.
- The wireframe rendering service (Bun :7610) does not need to be modified; we cancel from the Python side by checking the suspend flag before issuing each `httpx.post(/render)` call.
- The token counter cost (a tokenizer call per LLM request) is negligible compared to the LLM call itself and does not need to be itself cancelled.
